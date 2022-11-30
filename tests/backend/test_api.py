import json
from json import loads
from django.http import QueryDict
from django.utils.datastructures import MultiValueDict
from rest_framework.test import APITestCase, APIClient
import os
import django
from rest_framework.authtoken.models import Token
from backend.models import *

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shopping_service.settings')
django.setup()


class ApiTestCase(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(email='admin@admin.ad', password='a1d2m3i4n5', )
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key,)

        Shop.objects.create(id=1, name='shop', user_id=self.user.id, state=True)
        CategoryShop.objects.create(id=1, category_id=1, shop_id=1)
        Category.objects.create(id=1, name='category')
        Product.objects.create(id=1, name='product', category_id=1)
        ProductInfo.objects.create(id=1, model='model', product_id=1, shop_id=1, quantity=1, price=1, price_rrc=1)
        Parameter.objects.create(id=1, name='parameter')
        ProductParameter.objects.create(id=1, product_info_id=1, parameter_id=1, value='value')
        ConfirmEmailToken.objects.create(user_id=self.user.id)
        self.query_dict = QueryDict('', mutable=True, encoding='utf-8' )


    def test_user_register(self):
        new_user = self.client.post('/api/v1/user/register', data={'first_name': 'Admin',
                                                                   'last_name': 'Admin',
                                                                   'email': 'admin@admin.ru',
                                                                   'password': 'admin1254',
                                                                   'company': 'administration',
                                                                   'position': 'administrator'})
        new_user_check = User.objects.get(first_name='Admin')
        data = new_user.json()
        print('user_register', data)
        self.assertEqual(new_user_check.email, 'admin@admin.ru')
        self.assertEqual(True, data['Status'])
        self.assertEqual(200, new_user.status_code)

    def test_get_products(self):
        response = self.client.get('/api/v1/products/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        print('prod_list', data)
        for item in data:
            self.assertEqual(item['price'], 1)
            self.assertEqual(item['model'], 'model')
        self.assertEqual(len(data), 1)

    def test_get_products_parameters(self):
        """
        Проверка списка продуктов. Без указания необязательного параметра возвращает список продуктов,
        при указании параметра ?product_id=1 возвращает список параметров продукта со значениями
        """
        response = self.client.get('/api/v1/products/?product_id=1')
        data = response.json()
        print('prod_param', data)
        self.assertEqual(200, response.status_code)
        product_id = response.get('product_id')
        if product_id:
            self.assertEqual(data[0]['parameter'], ProductParameter.objects.filter(id=1)[0].parameter.name)
        if product_id is False:
            for item in data:
                self.assertContains('model', item.keys())

    def test_get_category(self):
        response = self.client.get('/api/v1/categories/')
        data = response.json()
        print('category', data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['name'], 'category')

    def test_get_shops(self):
        response = self.client.get('/api/v1/shops/')
        data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['count'], 1)
        print('shops', data)
        for item in data['results']:
            self.assertEqual(item['name'], 'shop')
            self.assertEqual(item['id'], 1)

    def test_post_basket(self):
        response = self.client.post('/api/v1/basket/', data={'items': '[{"quantity": 1, "product_info": 1}]'})
        data = response.json()
        print('create basket', data)
        self.assertEqual(True, data['Status'])
        self.assertEqual(200, response.status_code)

    def test_get_basket(self):
        self.client.post('/api/v1/basket/', data={'items': '[{"quantity": 1, "product_info": 1}]'})
        response = self.client.get('/api/v1/basket/')
        data = response.json()
        print('get basket', data)
        self.assertEqual(response.status_code, 200)

    def test_post_order(self):
        self.client.post('/api/v1/user/contact/', data={"city": "Moscow",
                                                        "street": "Lenina",
                                                        "phone": "7071016933"})
        self.client.post('/api/v1/basket/', data={'items': '[{"quantity": 1, "product_info": 1}]'})
        order_id = str(Order.objects.get(user_id=self.user.id, state='basket').id)
        contact_id = str(Contact.objects.get(user_id=self.user.id).id)
        response = self.client.post('/api/v1/order/', data={"id": order_id,
                                                            "contact": contact_id})
        print(type(response))
        data = response.json()
        print('create order', data)
        self.assertEqual(response.status_code, 200)

    def test_create_contact_info(self):
        count = Contact.objects.count()
        query_dict = QueryDict('', mutable=True)
        data = {
            'city': 'Chelyabinsk',
            'street': 'Lenina',
            'phone': 89099900999
        }
        query_dict.update(data)
        response = self.client.post('/api/v1/user/contact/', query_dict, content_type='application/json')

        data = response.json()
        print(data)
        # print('create_contact_info', data)
        self.assertEqual(response.status_code, 200)
        # self.assertEqual(Contact.objects.count(), count + 1)
