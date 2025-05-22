from django.db import models
from django.contrib.auth.models import User
from django.db.models import Avg, Count
from django.utils.text import slugify
from datetime import timedelta
from django.utils import timezone


# Reusable payment choices
PAYMENT_METHOD_CHOICES = [
    ('Cash', 'Cash'),
    ('SSLCommerz', 'SSLCommerz'),
]

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_image = models.ImageField(upload_to='profile_images/', blank=True, null=True)
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=15)
    city = models.CharField(max_length=100)
    postcode = models.CharField(max_length=10)

    def __str__(self):
        return self.user.username


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
    stock = models.PositiveIntegerField()
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
        self.save(update_fields=['rating'])  # Save the new rating to DB
        return avg

    def count_review(self):
        reviews = Review.objects.filter(product=self, status=True).aggregate(count=Count("id"))
        return int(reviews["count"]) if reviews["count"] is not None else 0

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
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)
    is_paid = models.BooleanField(default=False)
    price_at_added_time = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        unique_together = ('user', 'product')

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
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    ordered_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    shipping_address = models.CharField(max_length=255, blank=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='Cash')

    def __str__(self):
        return f"Order #{self.id} by {self.user.username} - {self.status}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)  # Price at time of order

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

    def save(self, *args, **kwargs):
        # Automatically mark SSLCommerz payments as Completed if not failed
        if self.payment_method == 'SSLCommerz' and self.status != 'Failed':
            self.status = 'Completed'
            self.order.status = 'Completed'  # Also update order status
            self.order.save(update_fields=['status'])
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Payment for Order #{self.order.id} - {self.status}"
