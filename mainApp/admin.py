from django.contrib import admin
from .models import UserProfile, Product, ProductImage, Review, Slider, CartItem, Order, OrderItem

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

class OrderItemInline(admin.TabularInline):  # 🔁 Move this ABOVE OrderAdmin
    model = OrderItem
    extra = 0

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

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'get_total_price', 'status', 'ordered_at')
    inlines = [OrderItemInline]  # ✅ Now OrderItemInline is defined above
    list_filter = ('status', 'ordered_at')
    search_fields = ('user__username',)

    def get_total_price(self, obj):
        total = 0
        for item in obj.items.all():
            price = item.product.get_discounted_price() if item.product else 0
            total += price * item.quantity
        return total
    get_total_price.short_description = 'Total Price'
