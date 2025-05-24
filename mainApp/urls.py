from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from .views import CustomPasswordChangeView

urlpatterns = [
    path('', views.home, name='home'),
    path('products/', views.product_list, name='product_list'),
    path('signup/', views.signup, name='signup'),
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('activate/<uidb64>/<token>/', views.activate, name='activate'),
    path('login/', views.custom_login, name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    path('profile/', views.profile, name='profile'),
    path('update_profile/', views.update_profile, name='update_profile'),
    # Keep only CustomPasswordChangeView for password change
    path('change-password/', CustomPasswordChangeView.as_view(), name='change_password'),

    path('cart/', views.cart_view, name='cart'),
    path('update-cart/', views.update_cart, name='update_cart'),
    path('clear-cart/', views.clear_cart, name='clear_cart'),
    path('add-to-cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('product/<int:id>/', views.product_detail, name='product_detail'),
    path('make-payment/', views.make_payment, name='make_payment'),
    path('process-payment/', views.process_payment, name='process_payment'),

    path('order-success/', views.order_success, name='order_success'),

    path('pay/<int:order_id>/', views.initiate_sslcommerz_payment, name='sslcommerz_payment'),
    # Updated to include order_id and point to your success handler
    path('sslcommerz/success/<int:order_id>/', views.sslcommerz_payment_success, name='payment_success'),
    path('sslcommerz/fail/', views.payment_fail, name='payment_fail'),
    path('sslcommerz/cancel/', views.payment_cancel, name='payment_cancel'),

    path('sslcommerz/success/<int:order_id>/', views.payment_success, name='payment_success'),
    path('sslcommerz/fail/<int:order_id>/', views.payment_fail, name='payment_fail'),
    path('sslcommerz/cancel/<int:order_id>/', views.payment_cancel, name='payment_cancel'),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
