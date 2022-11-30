import yaml
import re
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet
from backend.permissions import IsOwner, IsShop
from backend.tasks import new_order_send_message, new_user_register_send_message, canceled_order_send_mail
from requests import get
from distutils.util import strtobool
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.validators import URLValidator
from django.db import IntegrityError
from django.db.models import Q, Sum, F
from django.http import JsonResponse
from rest_framework.authtoken.models import Token
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from ujson import loads as load_json
from yaml import load as load_yaml, Loader
from backend.models import Shop, Category, ProductInfo, ProductParameter, Order, OrderItem, \
    Contact, ConfirmEmailToken, Product, Parameter, User
from backend.serializers import UserSerializer, CategorySerializer, ShopSerializer, ProductInfoSerializer, \
    OrderItemSerializer, OrderSerializer, ContactSerializer, ProductParameterSerializer


class RegisterAccount(APIView):
    """
    Класс для регистрации покупателей
    """

    def post(self, request):
        """
        Регистрация нового пользователя
        :param request: запрос пользователя с обязательными параметрами в теле запроса
        :return: добавляет нового пользователя и/или возвращает статус ответа
        """
        if {'first_name', 'last_name', 'email', 'password', 'company', 'position'}.issubset(
                request.data):  # проверяем обязательные аргументы
            try:
                validate_password(request.data['password'])
            except Exception as password_error:
                error_array = []
                for item in password_error:
                    error_array.append(item)
                return JsonResponse({'Status': False, 'Errors': {'password': error_array}})
            else:
                request.data.update({})
                user_serializer = UserSerializer(data=request.data)  # сохраняем пользователя
                if user_serializer.is_valid():
                    user = user_serializer.save()
                    user.set_password(request.data['password'])
                    user.save()
                    new_user_register_send_message.delay(user_id=user.id)
                    return JsonResponse({'Status': True})
                else:
                    return JsonResponse({'Status': False, 'Errors': user_serializer.errors})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class ConfirmAccount(APIView):
    """
    Класс для подтверждения почтового адреса
    """

    def post(self, request):
        """
        Подтверждение адреса электронной почты
        :param request: запрос пользователя с обязательными параметрами: email и token который придет на почту после
            регистрации пользователя
        :return: возвращает статус ответа
        """
        if {'email', 'token'}.issubset(request.data):  # проверяем обязательные аргументы
            token = ConfirmEmailToken.objects.filter(user__email=request.data['email'],
                                                     key=request.data['token']).first()
            if token:
                token.user.is_active = True
                token.user.save()
                token.delete()
                return JsonResponse({'Status': True})
            else:
                return JsonResponse({'Status': False, 'Errors': 'Неправильно указан токен или email'})

        return JsonResponse({'Status': False, 'Errors': 'All necessary arguments are not specified'})


class AccountDetailsViewSet(ModelViewSet):
    """
    Класс для работы данными пользователя
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsOwner]

    def list(self, request, *args, **kwargs):  # получить данные
        """
        Получение данных о пользователе
        :param request: запрос пользователя
        :return: возвращает полные данные о пользователе
        """
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        """
        Редактирование персональных данных пользователя
        :param request: запрос пользователя с обязательным параметром password
        :return: добавляет или обновляет данные и/или возвращает статус ответа
        """
        if 'password' in request.data:  # проверяем обязательные аргументы
            try:
                validate_password(request.data['password'])  # проверяем пароль на сложность
            except Exception as password_error:
                error_array = []
                for item in password_error:
                    error_array.append(item)
                return JsonResponse({'Status': False, 'Errors': {'password': error_array}})
            else:
                request.user.set_password(request.data['password'])
        user_serializer = UserSerializer(request.user, data=request.data, partial=True)  # проверяем остальные данные
        if user_serializer.is_valid():
            user_serializer.save()
            return JsonResponse({'Status': True})
        else:
            return JsonResponse({'Status': False, 'Errors': user_serializer.errors})


class LoginAccount(APIView):
    """
    Класс для авторизации пользователей
    """

    def post(self, request):
        """
        Авторизация пользователя методом POST
        :param request: запрос пользователя с email и password в теле запроса
        :return: возвращает токен пользователя и/или статус ответа
        """
        if {'email', 'password'}.issubset(request.data):
            user = authenticate(request, username=request.data['email'], password=request.data['password'])
            if user is not None:
                if user.is_active:
                    token, _ = Token.objects.get_or_create(user=user)
                    return JsonResponse({'Status': True, 'Token': token.key})
            return JsonResponse({'Status': False, 'Errors': 'Не удалось авторизовать'})
        return JsonResponse({'Status': False, 'Errors': 'All necessary arguments are not specified'})


class ContactView(APIView):
    """
    Класс для работы с контактами покупателей
    """

    def get(self, request):
        """
        Получение контактных данных
        :param request: запрос пользователя
        :return: возвращает список с контактными данными
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)
        contact = Contact.objects.filter(
            user_id=request.user.id)
        serializer = ContactSerializer(contact, many=True)
        return Response(serializer.data)

    def post(self, request):
        """
        Добавление контактных данных
        :param request: запрос ползователя с данными в теле запроса
        :return: добавляет данные и/или возвращает статус ответа
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)
        if {'city', 'street', 'phone'}.issubset(request.data):  # проверка на заполнение обязательных полей
            request.data._mutable = True
            regex = r"(\+7|7|8)*[\s\(]*(\d{3})[\)\s-]*(\d{3})[-]*(\d{2})[-]*(\d{2})[\s\(]*"
            phone = request.data['phone']
            phone_correct = r"+7(\2)\3-\4-\5"  # корректирование номера телефона
            corrected_phone = re.sub(regex, phone_correct, phone)
            request.data.update({'user': request.user.id, 'phone': corrected_phone})
            serializer = ContactSerializer(data=request.data)

            if serializer.is_valid():
                serializer.save()
                return JsonResponse({'Status': True})
            else:
                return JsonResponse({'Status': False, 'Errors': serializer.errors})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    @action(methods='DELETE', detail=False)
    def delete(self, request):
        """
        Удаление контактных данных
        :param request: запрос пользователя с идентификатором списка контактных данных
        :return: удаляет контактные данные и возвращает количество удаленных объектов
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)
        items_sting = request.data.get('items')
        if items_sting:
            items_list = items_sting.split(',')
            query = Q()
            objects_deleted = False
            for contact_id in items_list:
                if contact_id.isdigit():
                    query = query | Q(user_id=request.user.id, id=contact_id)
                    objects_deleted = True
            if objects_deleted:
                deleted_count = Contact.objects.filter(query).delete()[0]
                return JsonResponse({'Status': True, 'Удалено объектов': deleted_count})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    def put(self, request):
        """
        Изменение контактных данных
        :param request: запрос пользователя с обновленными данными в теле запроса
        :return: обновляет данные и/или возвращает статус ответа
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)
        if 'id' in request.data:
            if request.data['id'].isdigit():
                contact = Contact.objects.filter(id=request.data['id'], user_id=request.user.id).first()
                print(contact)
                if contact:
                    serializer = ContactSerializer(contact, data=request.data, partial=True)
                    if serializer.is_valid():
                        serializer.save()
                        return JsonResponse({'Status': True})
                    else:
                        JsonResponse({'Status': False, 'Errors': serializer.errors})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class CategoryView(ListAPIView):
    """
    Класс для просмотра списка категорий
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class ShopView(ListAPIView):
    """
    Класс для просмотра списка магазинов
    """
    queryset = Shop.objects.filter(state=True)
    serializer_class = ShopSerializer


class ProductInfoView(APIView):
    """
    Класс для поиска товаров
    """

    def get(self, request):
        """
        Получение списка товаров или характеристики товара
        :param request: запрос пользователя с указанием или без указания необязательных параметров
        :return: без указания параметров возвращает список всех товаров
                при указании category_id=<int> возвращает отсортированный по категории список товаров
                при указании shop_id=<int> возвращает список товаров определенного магазина
                при указании product_id=<int> возвращает список с характеристиками определенного товара
        """
        try:
            query = Q(shop__state=True)
            shop_id = request.query_params.get('shop_id')
            category_id = request.query_params.get('category_id')
            product_id = request.query_params.get('product_id')
            if product_id:
                queryset = ProductParameter.objects.filter(product_info__product=product_id)
                serializer = ProductParameterSerializer(queryset, many=True)
                return Response(serializer.data)  # возвращает характеристики продукта по id
            if shop_id:
                query = query & Q(shop_id=shop_id)
            if category_id:
                query = query & Q(product__category_id=category_id)  # фильтруем и отбрасываем дуликаты
            queryset = ProductInfo.objects.filter(
                query).select_related(
                'shop', 'product__category').prefetch_related(
                'product_parameter__parameter').distinct()
            serializer = ProductInfoSerializer(queryset, many=True)
            return Response(serializer.data)
        except ValueError as error:
            return JsonResponse({'Status': False, 'Error': error})


class BasketViewSet(ModelViewSet):
    """
    Класс для работы с корзиной пользователя
    """
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated, IsOwner]

    def list(self, request, *args, **kwargs):
        """
        Получение информации о корзине
        :param request: запрос пользователя
        :return: возвращает id заказа, список товаров добавленных в корзину, статус заказа, дату формирования,
        общую сумму заказа и контактные данные покупателя
        """
        basket = Order.objects.filter(
            user_id=request.user.id, state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameter__parameter').annotate(
            total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))).distinct()
        serializer = OrderSerializer(basket, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        """
        Создание корзины или добавление новых товаров в уже существующую
        :param request: запрос клиента со словарем в теле запроса
        формата - "items": [{"quantity":<int>, "product_info":<int>},{...}]
        :return: создает новый заказ со статусом basket, возвращает статус запроса
        и количество добавленных наименований товаров
        """
        items_sting = request.data.get('items')
        if items_sting:
            try:
                items_dict = load_json(items_sting)
            except ValueError:
                JsonResponse({'Status': False, 'Errors': 'Неверный формат запроса'})
            else:
                basket, _ = Order.objects.get_or_create(user_id=request.user.id, state='basket')
                objects_created = 0
                for order_item in items_dict:
                    order_item.update({'order': basket.id})
                    serializer = OrderItemSerializer(data=order_item)
                    if serializer.is_valid():
                        try:
                            serializer.save()
                        except IntegrityError as error:
                            return JsonResponse({'Status': False, 'Errors': str(error)})
                        else:
                            objects_created += 1  # счетчик количества созданных объектов
                    else:
                        JsonResponse({'Status': False, 'Errors': serializer.errors})

                return JsonResponse({'Status': True, 'Создано объектов': objects_created})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    @action(detail=False, methods=['DELETE'], url_path='delete')
    def my_custom_destroy(self, request):
        """
        Удаление товаров из корзины
        При выполнении этого запроса, к базовому url этого класса нужно добавить /delete/
        :param request: запрос пользователя со строкой позиций товаров в корзине перечисленных
        через запятую формата - {"items": "<int>,<int>"}
        :return: удааляет выбранные позиции и возвращает количество удаленных наименований товаров
        """
        items_sting = request.data.get('items')
        if items_sting:
            items_list = items_sting.split(',')
            basket, _ = Order.objects.get_or_create(user_id=request.user.id, state='basket')
            query = Q()
            objects_deleted = False
            for order_item_id in items_list:
                if order_item_id.isdigit():
                    query = query | Q(order_id=basket.id, id=order_item_id)
                    objects_deleted = True
            if objects_deleted:
                deleted_count = OrderItem.objects.filter(query).delete()[0]
                if OrderItem.objects.filter(order__user_id=request.user.id).count() == 0:
                    Order.objects.filter(user_id=request.user.id).delete()
                    return JsonResponse({'Status': True, 'Message': 'Корзина удалена', })
                return JsonResponse({'Status': True, 'Удалено объектов': deleted_count})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    @action(detail=False, methods=['PUT'], url_path='put')
    def my_custom_update(self, request):
        """
        Обновление количества ранее добавленных товаров в корзине
        При выполнении этого запроса, к базовому url этого класса нужно добавить /put/
        :param request: запрос пользователя со строкой внутри словаря с id позиций товаров в корзине перечисленных
        через запятую формата - "items": [{"quantity":<int>, "id":<int>},{...}] - где id  это id позиции в корзине
        :return: обновляет количество выбранных позиций и возвращает количество обновленых товаров
        """
        items_sting = request.data.get('items')
        if items_sting:
            try:
                items_dict = load_json(items_sting)
            except ValueError:
                return JsonResponse({'Status': False, 'Errors': 'Неверный формат запроса'})
            else:
                basket, _ = Order.objects.get_or_create(user_id=request.user.id, state='basket')
                objects_updated = 0
                for order_item in items_dict:
                    if type(order_item['id']) == int and type(order_item['quantity']) == int:
                        objects_updated += OrderItem.objects.filter(order_id=basket.id, id=order_item['id']).update(
                            quantity=order_item['quantity'])

                return JsonResponse({'Status': True, 'Обновлено объектов': objects_updated})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class OrderViewSet(ModelViewSet):
    """
    Класс для получения и размешения заказов пользователями
    """
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated, IsOwner]

    def list(self, request, *args, **kwargs):
        """
        Получение информации о заказе
        :param request: запрос пользователя
        :return: возвращает id заказа, список товаров, статус заказа, дату формирования,
        общую сумму заказа и контактные данные покупателя
        """
        order = Order.objects.filter(  # формирование информации
            user_id=request.user.id).exclude(state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameter__parameter').select_related('contact').annotate(
            total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))).distinct()
        serializer = OrderSerializer(order, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        """
        Размещение заказа из корзины
        :param request: запрос пользователя со словарем формата - {"id":<int>, "contact":<int>}
        - где id  это id заказа, contact это id контакта пользователя
        :return: меняет статус заказа с basket на new, возвращает статус ответа и уведомление об отправке пользователю
        сообщения с информацией о заказе
        """
        if {'id', 'contact'}.issubset(request.data):
            if request.data['id'].isdigit():
                try:
                    order = Order.objects.filter(
                        user_id=request.user.id, id=request.data['id'])
                    contact_id = request.data['contact']
                    for item in OrderItem.objects.filter(order_id=request.data['id'], order__user_id=request.user.id):
                        if item.order.state == 'basket':
                            new_quantity = item.product_info.quantity - item.quantity
                            if int(new_quantity) < 0:
                                return JsonResponse(
                                    {'Status': False, 'Errors': 'Выбрано больше позиций, чем есть в наличии. '
                                                                'Выберете другое количество'})
                            if not Contact.objects.filter(id=contact_id, user_id=request.user.id):
                                return JsonResponse(
                                    {'Status': False, 'Result': 'Укажите контактные данные для доставки товара'})
                            ProductInfo.objects.filter(quantity=item.product_info.quantity,
                                                       id=item.product_info.id).update(
                                quantity=new_quantity)  # удаление позиций товара из базы после подтверждения заказа
                        else:
                            return JsonResponse({'Status': False, 'Errors': 'Basket is empty'})
                    is_updated = order.update(
                        contact_id=contact_id,
                        state='new')
                    if is_updated:
                        new_order_send_message.delay(
                            user_id=request.user.id,
                            order_id=request.data['id'])  # отправка уведомления о заказе на email пользователя
                        return JsonResponse({'Status': True, 'Result': 'Сообщение отправлено'})
                except Exception as error:
                    print(error)
                    return JsonResponse({'Status': False, 'Errors': f'{error}'})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    @action(detail=False, methods=['DELETE'], url_path='delete')
    def my_custom_destroy(self, request):
        """
        Отмена и удаление оформленного заказа
        При выполнении этого запроса, к базовому url этого класса нужно добавить /delete/
        :param request: запрос пользователя с id заказа формата - {"id":<int>}
        :return: удааляет заказ со статусом new и добавляет обратно в базу данных все позиции из заказа,
        возвращает статус ответа и сообщение с номером удаленного заказа
        """
        try:
            if Order.objects.filter(user_id=request.user.id, state='new', id=request.data['id']):
                for item in OrderItem.objects.filter(order_id=request.data['id']):
                    if item.order.state == 'new':
                        new_quantity = item.product_info.quantity + item.quantity
                        ProductInfo.objects.filter(quantity=item.product_info.quantity,
                                                   id=item.product_info.id).update(
                            quantity=new_quantity)  # возвращение количества отмененных позиций
                Order.objects.filter(user_id=request.user.id, state='new',
                                     id=request.data['id']).delete()  # удаление отмененного заказа
                canceled_order_send_mail.delay(user_id=request.user.id, order_id=request.data[
                    'id'])  # отправка уведомления об отмене заказа на email пользователя
                return JsonResponse({'Status': True, 'Message': f'Order # {request.data["id"]} has been canceled.'})
            else:
                return JsonResponse({'Status': False, 'Message': 'Order not found'})
        except BaseException as error:
            return JsonResponse({'Status': False, 'Errors': 'error'})


class PartnerStateViewSet(ModelViewSet):
    """
    Класс для работы со статусом поставщика
    """
    queryset = Shop.objects.all()
    serializer_class = ShopSerializer
    permission_classes = [IsAuthenticated, IsOwner, IsShop]

    def list(self, request, *args, **kwargs):
        """
        Получение текущего статуса магазина
        :param request: запрос пользователя
        :return: возвращает id магазина, название, статус магазина (принимает или не принимает заказы)
        """
        shop = request.user.shop
        serializer = ShopSerializer(shop)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        """
        Изменение текущего статуса магазина
        :param request: запрос пользователя со статусом формата - {"state":<bool>} где bool = 0 или 1
        :return: меняет статус магазина и возвращает статус ответа
        """
        state = request.data.get('state')
        if state:
            try:
                Shop.objects.filter(user_id=request.user.id).update(state=strtobool(state))
                return JsonResponse({'Status': True})
            except ValueError as error:
                return JsonResponse({'Status': False, 'Errors': str(error)})

        return JsonResponse({'Status': False, 'Errors': 'All necessary arguments are not specified'})


class PartnerOrdersViewSet(ModelViewSet):
    """
    Класс для получения заказов поставщиками
    """
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated, IsOwner, IsShop]

    def list(self, request, *args, **kwargs):
        """
        Получение списка заказов магазином
        :param request: запрос пользователя
        :return: возвращает id заказа, список товаров, статус заказа, дату формирования,
        общую сумму заказа и контактные данные покупателя
        """
        try:
            order = Order.objects.filter(
                ordered_items__product_info__shop__user_id=request.user.id).exclude(state='basket').prefetch_related(
                'ordered_items__product_info__product__category',
                'ordered_items__product_info__product_parameter__parameter').select_related('contact').annotate(
                total_sum=Sum(F('ordered_items__quantity') *
                              F('ordered_items__product_info__price'))).distinct()  # структурирование информации
            serializer = OrderSerializer(order, many=True)
            return Response(serializer.data)
        except ValueError as error:
            return JsonResponse({'Status': False, 'Error': error})


class PartnerUpdate(APIView):
    """
    Класс для обновления прайса от поставщика
    """

    def post(self, request, *args, **kwargs):
        """
        Добавление и обновление информации от поставщика
        :param request: запрос пользователя с указанием минимум одного из двух параметров в теле запроса
        в которых нужно указать путь к данным формата yaml
        пример -
        {'url': 'https://path_to_file.yaml'} путь к url с данными
        {'file': 'data/data.yaml'} относительный или абсолютный путь к yaml файлу
        :return: добавляет информацию в базу данных и возвращает статус ответа
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)
        if request.user.type != 'shop':  # проверка на тип пользователя (магазин)
            return JsonResponse({'Status': False, 'Error': 'Only for shop'}, status=403)
        try:
            user_id = request.user.id
            filename = request.data.get('file')
            url = request.data.get('url')
            if filename:  # извлечение информации из файла
                with open(filename, 'r', encoding='utf-8') as stream:
                    data = yaml.safe_load(stream)
            elif url and filename is None:  # извлечение информации с url
                validate_url = URLValidator()
                validate_url(url)
                stream = get(url).content
                data = load_yaml(stream, Loader=Loader)
            else:
                JsonResponse({'Status': False, 'Error': 'The source of information is incorrectly specified'})
            try:  # загрузка информации в базу данных
                shop, _ = Shop.objects.get_or_create(name=data['shop'], user_id=user_id)
            except IntegrityError as error:
                return JsonResponse({'Status': False, 'Error': f'{error}'})
            Shop.objects.filter(user_id=user_id).update(filename=filename, url=url)
            for category in data['categories']:
                category_object, _ = Category.objects.get_or_create(id=category['id'], name=category['name'])
                category_object.shops.add(shop.id)
                category_object.save()
            ProductInfo.objects.filter(shop_id=shop.id).delete()
            for item in data['goods']:
                product, _ = Product.objects.get_or_create(name=item['name'], category_id=item['category'],
                                                           id=item['id'])
                product_info = ProductInfo.objects.create(product_id=product.id,
                                                          model=item['model'],
                                                          price=item['price'],
                                                          price_rrc=item['price_rrc'],
                                                          quantity=item['quantity'],
                                                          shop_id=shop.id)
                for name, value in item['parameters'].items():
                    parameter_object, _ = Parameter.objects.get_or_create(name=name)
                    ProductParameter.objects.create(product_info_id=product_info.id,
                                                    parameter_id=parameter_object.id,
                                                    value=value)
            return JsonResponse({'Status': True})
        except BaseException as error:
            return JsonResponse({"Status": "False", "Error": f"{error.__str__()}"})
