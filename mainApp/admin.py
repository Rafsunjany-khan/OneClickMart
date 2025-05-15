from django.contrib import admin
from .models import UserProfile, Product, ProductImage, Review, Slider, CartItem, Order, OrderItem

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'discount_percentage', 'stock', 'available', 'rating')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductImageInline]
    search_fields = ('name', 'description')
    list_filter = ('available',)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'city', 'postcode')
    search_fields = ('user__username', 'phone_number', 'city')

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('product__name', 'user__username', 'review')

@admin.register(Slider)
class SliderAdmin(admin.ModelAdmin):
    list_display = ('title', 'subtitle', 'created_at')

class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 1

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'get_total_price', 'status', 'ordered_at')
    inlines = [OrderItemInline]
    list_filter = ('status', 'ordered_at')
    search_fields = ('user__username',)

    def get_total_price(self, obj):
        return sum(item.product.get_discounted_price() * item.quantity for item in obj.orderitem_set.all())
    get_total_price.short_description = 'Total Price'
