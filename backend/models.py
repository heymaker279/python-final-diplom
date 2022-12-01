from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_rest_passwordreset.tokens import get_token_generator

ORDER_CHOICES = (
    ('confirmed', 'подтвержден'),
    ('basket', 'в корзине'),
    ('canceled', 'отменен'),
    ('sent', 'отправлен'),
    ('assembly', 'в процессе сборки'),
    ('delivered', 'доставлен'),
    ('new', 'новый'),
)

USER_TYPE_CHOICES = (
    ('shop', 'Магазин'),
    ('buyer', 'Покупатель'),

)


class UserManager(BaseUserManager):
    """
    Миксин для управления пользователями
    """
    def _create_user(self, email, password, **extra_fields):
        """
        Create and save a user with the given username, email, and password.
        """
        if not email:
            raise ValueError('The given email must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Стандартная модель пользователей
    """
    REQUIRED_FIELDS = []
    objects = UserManager()
    USERNAME_FIELD = 'email'
    email = models.EmailField(_('email address'), unique=True)
    company = models.CharField(verbose_name='Компания', max_length=40, blank=True)
    position = models.CharField(verbose_name='Должность', max_length=40, blank=True)
    username_validator = UnicodeUsernameValidator()
    username = models.CharField(
        _('username'),
        max_length=150,
        help_text=_('Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.'),
        validators=[username_validator],
        error_messages={
            'unique': _("A user with that username already exists."),
        },
    )
    is_active = models.BooleanField(
        _('active'),
        default=True,
        help_text=_(
            'Designates whether this user should be treated as active. '
            'Unselect this instead of deleting accounts.'
        ),
    )
    type = models.CharField(verbose_name='Тип пользователя', choices=USER_TYPE_CHOICES, max_length=5, default='buyer')

    def __str__(self):
        return f'{self.first_name} {self.last_name}'

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = "Список пользователей"
        ordering = ('email',)


class Shop(models.Model):
    """
    Модель с информацией о магазине
    """
    name = models.CharField(max_length=50, verbose_name='Название', unique=True)
    url = models.URLField(verbose_name='Ссылка', null=True, blank=True)  # url ссылка на данные о товарах от поставщика в yaml формате
    filename = models.CharField(verbose_name='путь к файлу', max_length=200, null=True, blank=True)  # путь к файлу с данными о товаре от поставщика
    state = models.BooleanField(default=True, verbose_name='Статус получения заказов')
    user = models.OneToOneField(User, verbose_name='пользователь', blank=True, null=True, on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Магазин'
        verbose_name_plural = "Список магазинов"
        ordering = ('-name',)

    def __str__(self):
        return self.name


class Category(models.Model):
    """
    Модель с информацией о категориях товаров
    """
    name = models.CharField(max_length=50, verbose_name='Название')
    shops = models.ManyToManyField(Shop, verbose_name='Магазины', blank=True, through='CategoryShop')

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = "Список категорий"
        ordering = ('-name',)

    def __str__(self):
        return self.name


class CategoryShop(models.Model):
    """
    Промежуточная таблица связывающая категории и магазины
    """
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='category_shop')
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='category_shop')


class Product(models.Model):
    """
    Модель с названием товаров и их категорий
    """
    name = models.CharField(max_length=100, verbose_name='Название')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, verbose_name='Категория',
                                 related_name='products', blank=True)

    class Meta:
        verbose_name = 'Продукт'
        verbose_name_plural = "Список продуктов"
        ordering = ('-name',)

    def __str__(self):
        return self.name


class ProductInfo(models.Model):
    """
    Модель с информацией о товаре
    """
    model = models.CharField(max_length=80, verbose_name='Модель', blank=True)
    product = models.ForeignKey(Product, verbose_name='Продукт', related_name='product_infos', blank=True,
                                on_delete=models.CASCADE)
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, verbose_name='Магазин', blank=True,
                             related_name='product_infos')
    quantity = models.PositiveIntegerField(verbose_name='Колличество')
    price = models.PositiveIntegerField(verbose_name='Цена')
    price_rrc = models.PositiveIntegerField(verbose_name='Рекомендуемая розничная цена')

    class Meta:
        verbose_name = 'Информация о продукте'
        verbose_name_plural = "Иформационный список о продуктах"
        constraints = [
            models.UniqueConstraint(fields=['product', 'shop', 'id'], name='unique_product_info'),
        ]

    def __str__(self):
        return self.product.name


class Parameter(models.Model):
    """
    Модель с названиями параметров товаров
    """
    name = models.CharField(max_length=50, verbose_name='Название')

    class Meta:
        verbose_name = 'Имя параметра'
        verbose_name_plural = "Список имен параметров"
        ordering = ('-name',)

    def __str__(self):
        return self.name


class ProductParameter(models.Model):
    """
    Модель с информацией о параметрах товаров
    """
    product_info = models.ForeignKey(ProductInfo, verbose_name='Информация о продукте',
                                     related_name='product_parameter', blank=True,
                                     on_delete=models.CASCADE)
    parameter = models.ForeignKey(Parameter, verbose_name='Параметр', blank=True,
                                  related_name='product_parameter',
                                  on_delete=models.CASCADE)
    value = models.CharField(verbose_name='Значение', max_length=100)

    class Meta:
        verbose_name = 'Параметр'
        verbose_name_plural = "Список параметров"
        constraints = [
            models.UniqueConstraint(fields=['product_info', 'parameter'], name='unique_product_parameter'),
        ]

    def __str__(self):
        return self.parameter.name


class Order(models.Model):
    """
    Модель с информацией о заказе
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Пользователь', related_name='orders')
    dt = models.DateTimeField(auto_now_add=True, verbose_name='время создания заказа')
    state = models.CharField(max_length=35, verbose_name='Статус заказа', choices=ORDER_CHOICES, default="in_process")
    contact = models.ForeignKey('Contact', verbose_name='Контакт', blank=True, null=True, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Заказ"
        ordering = ("-dt",)
        verbose_name_plural = "Список заказов"

    def __str__(self):
        return str(self.dt)


class OrderItem(models.Model):
    """
    Модель с информацией о количестве экземпляров товаров в заказе
    """
    order = models.ForeignKey(Order, on_delete=models.CASCADE, verbose_name="Заказ", related_name="ordered_items")
    product_info = models.ForeignKey(ProductInfo, on_delete=models.CASCADE, verbose_name="Инфо о продукте",
                                     related_name="ordered_items", blank=True)
    quantity = models.PositiveIntegerField(verbose_name='Количество')

    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Список заказанных позиций"
        constraints = [
            models.UniqueConstraint(fields=['order_id', 'product_info'], name='unique_order_item'),

        ]


class Contact(models.Model):
    """
    Модель с информацией о контактных данных пользователей
    """
    user = models.ForeignKey(User, verbose_name='Пользователь', related_name='contacts', null=True, blank=True,
                             on_delete=models.CASCADE)
    apt = models.CharField(max_length=70, verbose_name="Квартира", blank=True)
    building = models.CharField(max_length=70, verbose_name="Строение", blank=True)
    street = models.CharField(max_length=150, verbose_name="Улица", blank=True)
    city = models.CharField(max_length=70, verbose_name="Город", blank=True)
    structure = models.CharField(max_length=100, verbose_name="Корпус", blank=True)
    phone = models.CharField(max_length=20, verbose_name='Телефон', blank=True)
    house = models.CharField(max_length=15, verbose_name='Дом', blank=True)

    class Meta:
        verbose_name = "Карточка контактов клиента"
        verbose_name_plural = "Карточки клиентов"

    def __str__(self):
        return f'{self.city} {self.street} {self.house}'


class ConfirmEmailToken(models.Model):
    """
    Модель токена подтверждения электронной почты
    """

    class Meta:
        verbose_name = 'Токен подтверждения Email'
        verbose_name_plural = 'Токены подтверждения Email'

    @staticmethod
    def generate_key():
        """ generates a pseudo random code using os.urandom and binascii.hexlify """
        return get_token_generator().generate_token()

    user = models.ForeignKey(
        User,
        related_name='confirm_email_tokens',
        on_delete=models.CASCADE,
        verbose_name=_("The User which is associated to this password reset token")
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("When was this token generated")
    )

    # Key field, though it is not the primary key of the model
    key = models.CharField(
        _("Token"),
        max_length=64,
        db_index=True,
        unique=True
    )

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = self.generate_key()
        return super(ConfirmEmailToken, self).save(*args, **kwargs)

    def __str__(self):
        return "Password reset token for user {user}".format(user=self.user)
