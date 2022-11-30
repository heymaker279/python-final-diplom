import json

from django.core.mail import send_mail
from django.db.models import Sum, F
from django.dispatch import receiver
from django_rest_passwordreset.signals import reset_password_token_created
from shopping_service.celery import app
from shopping_service.settings import EMAIL_HOST_USER
from backend.models import Order, User, ConfirmEmailToken, ProductInfo

from_email = EMAIL_HOST_USER


@receiver(reset_password_token_created)
@app.task()
def password_reset_token_created_message(reset_password_token, **kwargs):
    """
    Отправляем письмо с токеном для сброса пароля
    :return: отправляет email с токеном для сброса пароля при создании нового пользователя
    """
    data = reset_password_token.key
    subject, recipient_list = f"Password Reset Token for {reset_password_token.user}", [reset_password_token.user.email]
    send_mail(subject, data, from_email, recipient_list)


@app.task()
def new_user_register_send_message(user_id, **kwargs):
    """
    отправляем письмо с подтрердждением почты
    :param user_id: id пользователя
    :return: отправляет email с токеном
    """
    token, _ = ConfirmEmailToken.objects.get_or_create(user_id=user_id)
    data = f"Token for reset your password # {token.key} "

    subject, recipient_list = f"Password Reset Token for {token.user.email}", [token.user.email, ]
    send_mail(subject, data, from_email, recipient_list)


@app.task()
def new_order_send_message(user_id, order_id, **kwargs):
    """
    Отправляем письмо с подтверждением заказа
    :param user_id: id пользователя
    :param order_id: id заказа
    :return: отправляет письмо с данными о заказе и контактными данными покупателя
    """
    try:
        order = Order.objects.filter(
            user_id=user_id, id=order_id).exclude(state='basket').select_related('contact').annotate(
            total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))).distinct()
        user = User.objects.get(id=user_id)
        content = []
        for item in order:
            data = [f'Your order # {item.id} has been processed\nState: {item.state},\nTotal sum: {item.total_sum}'
                    f'\nRecipient name: {item.contact.user}'
                    f'\nAddress: {item.contact.city}, {item.contact.street}, {item.contact.house}'
                    f'\nPhone: {item.contact.phone}']
            content.append(*data)
        subject, recipient_list = f"Обновление статуса заказа", [user.email, ]
        send_mail(subject, *content, from_email, recipient_list)
    except BaseException as error:
        raise error


@app.task()
def canceled_order_send_mail(user_id, order_id, **kwargs):
    """
    Отправляем письмо об удалении
    :param user_id: id пользователя
    :param order_id: id заказа
    :return: отправляет письмо с подтверждением об удалении заказа
    """
    user = User.objects.get(id=user_id)
    data = f"Your order # {str(order_id)}  has been cancelled."
    subject, recipient_list = f"Обновление статуса заказа", [user.email, ]
    send_mail(subject, data, from_email, recipient_list)
