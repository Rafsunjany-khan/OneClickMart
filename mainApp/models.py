from django.db import models
from django.contrib.auth.models import User
from django.db.models import Avg, Count
from django.utils.text import slugify
from datetime import timedelta
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, UniqueConstraint

# Reusable payment choices
PAYMENT_METHOD_CHOICES = [
    ('Cash', 'Cash'),
    ('SSLCommerz', 'SSLCommerz'),
]

class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class Product(TimeStampedModel):
    name = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, blank=True, null=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    stock = models.PositiveIntegerField(default=0)
    available = models.BooleanField(default=True)
    unit = models.CharField(max_length=100, null=True, blank=True)
    rating = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def discount_price(self):
        if self.discount_percentage <= 0 or self.discount_percentage > 100:
            return self.price
        discount_amount = self.price * (self.discount_percentage / 100)
        discounted_price = self.price - discount_amount
        return max(discounted_price, 0)

    @property
    def savings(self):
        return self.price - self.discount_price

    def get_discounted_price(self):
        return self.discount_price if self.discount_percentage > 0 else self.price

    @property
    def is_new_arrival(self):
        # Consider products added within the last 7 days as new arrivals
        return self.created_at >= timezone.now() - timedelta(days=5)

    def averageReview(self):
        reviews = Review.objects.filter(product=self, status=True).aggregate(average=Avg("rating"))
        avg = float(reviews["average"]) if reviews["average"] is not None else 0
        self.rating = avg
        self.save(update_fields=['rating'])
        return avg

    def count_review(self):
        reviews = Review.objects.filter(product=self, status=True).aggregate(count=Count("id"))
        return int(reviews["count"]) if reviews["count"] is not None else 0


    def reduce_stock(self, quantity):
        if quantity > 0:
            self.stock = max(self.stock - quantity, 0)
            self.save(update_fields=['stock'])

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.name

class ProductImage(models.Model):
    product = models.ForeignKey(Product, related_name="images", on_delete=models.CASCADE)
    image = models.ImageField(upload_to="products/images")

    def __str__(self):
        return f"Image for {self.product.name}"


class Review(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reviews")
    rating = models.FloatField()
    review = models.TextField(max_length=500, blank=True)
    status = models.BooleanField(default=True)

    def __str__(self):
        return f"Review by {self.user.username} for {self.product.name}"


class Slider(TimeStampedModel):
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, blank=True)
    image = models.ImageField(upload_to="sliders")

    def __str__(self):
        return self.title


class CartItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cart_items')
    order = models.ForeignKey('Order', on_delete=models.CASCADE, related_name='cart_items', null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)
    is_paid = models.BooleanField(default=False)
    price_at_added_time = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        constraints = [
            UniqueConstraint(fields=['user', 'product'], condition=Q(order__isnull=True),
                             name='unique_active_cart_per_product')
        ]

    def clean(self):
        if self.order is None:
            qs = CartItem.objects.filter(user=self.user, product=self.product, order__isnull=True)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError("This product is already in your active cart.")

    def save(self, *args, **kwargs):
        if not self.price_at_added_time:
            self.price_at_added_time = self.product.get_discounted_price()
        self.clean()
        super().save(*args, **kwargs)

    @property
    def total_price(self):
        return self.price_at_added_time * self.quantity

    def __str__(self):
        return f"{self.quantity} x {self.product.name} for {self.user.username}"


class Order(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Processing', 'Processing'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
        ('Failed', 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    ordered_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    shipping_address = models.CharField(max_length=255, blank=True)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='Cash')

    @property
    def is_paid(self):
        return hasattr(self, 'payment') and self.payment.status == 'Completed'

    def __str__(self):
        return f"Order #{self.id} by {self.user.username} - {self.status}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)  # Price at time of order

    def save(self, *args, **kwargs):
        if not self.price or self.price == 0:
            self.price = self.product.price  # or your discounted price method
        super().save(*args, **kwargs)


    @property
    def total_price(self):
        return self.price * self.quantity

    def __str__(self):
        product_name = self.product.name if self.product else 'Deleted Product'
        return f"{self.quantity} x {product_name}"


class Payment(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Completed', 'Completed'),
        ('Failed', 'Failed'),
    ]

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payment')
    transaction_id = models.CharField(max_length=255)
    payment_method = models.CharField(max_length=100, choices=PAYMENT_METHOD_CHOICES, default='SSLCommerz')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    paid_at = models.DateTimeField(auto_now_add=True)

    def update_product_stock(self):
        for item in self.order.items.all():
            product = item.product
            if product and product.stock >= item.quantity:
                product.stock -= item.quantity
            elif product:
                product.stock = 0
            product.save(update_fields=['stock'])

    def save(self, *args, **kwargs):
        is_new_payment = self.pk is None
        previous_status = None

        if not is_new_payment:
            previous_status = Payment.objects.get(pk=self.pk).status

        super().save(*args, **kwargs)

        if self.status == 'Completed' and (is_new_payment or previous_status != 'Completed'):
            with transaction.atomic():
                self.order.status = 'Completed'
                self.order.save(update_fields=['status'])
                self.update_product_stock()

    def __str__(self):
        return f"Payment for Order #{self.order.id} - {self.status}"

