from django.urls import path, re_path
from rest_framework.routers import DefaultRouter
from django_rest_passwordreset.views import reset_password_request_token, reset_password_confirm
from backend.views import PartnerUpdate, RegisterAccount, LoginAccount, CategoryView, ShopView, \
    BasketViewSet, \
    AccountDetailsViewSet, ConfirmAccount, \
    ProductInfoView, ContactView, OrderViewSet, PartnerStateViewSet, PartnerOrdersViewSet

r = DefaultRouter()
r.register('basket', BasketViewSet)
r.register('order', OrderViewSet)
r.register('partner/state', PartnerStateViewSet)
r.register('partner/orders', PartnerOrdersViewSet)
r.register('user/details', AccountDetailsViewSet)

app_name = 'backend'
urlpatterns = [
    re_path(r'^user/contact', ContactView.as_view(), name='contact'),
    re_path(r'^partner/update', PartnerUpdate.as_view(), name='partner-update'),
    path('user/register', RegisterAccount.as_view(), name='user-register'),
    path('user/register/confirm', ConfirmAccount.as_view(), name='user-register-confirm'),
    re_path(r'^user/login', LoginAccount.as_view(), name='user-login'),
    re_path(r'^user/password_reset', reset_password_request_token, name='password-reset'),
    re_path(r'^user/password_reset/confirm', reset_password_confirm, name='password-reset-confirm'),
    re_path(r'^categories', CategoryView.as_view(), name='categories'),
    re_path(r'^shops', ShopView.as_view(), name='shops'),
    re_path(r'^products', ProductInfoView.as_view(), name='products'),
] + r.urls
