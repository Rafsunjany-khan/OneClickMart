from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.home, name='home'),
    path('products/', views.product_list, name='product_list'),
    path('cart/', views.cart_view, name='cart'),
    path('update-cart/', views.update_cart, name='update_cart'),
    path('clear-cart/', views.clear_cart, name='clear_cart'),
    path('add-to-cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('product/<int:id>/', views.product_detail, name='product_detail'),
    path('make-payment/', views.make_payment, name='make_payment'),
    path('process-payment/', views.process_payment, name='process_payment'),
    path('process-payment/<int:order_id>/', views.process_payment, name='process_payment'),


    path('order-success/', views.order_success, name='order_success'),

    path('pay/<int:order_id>/', views.initiate_sslcommerz_payment, name='sslcommerz_payment'),
    path('pay/<int:order_id>/', views.initiate_sslcommerz_payment, name='sslcommerz_payment'),
    path('payment/success/', views.sslcommerz_success, name='sslcommerz_success'),
    path('sslcommerz/success/', views.sslcommerz_payment_success, name='payment_success'),
    path('sslcommerz/fail/<int:order_id>/', views.payment_fail, name='payment_fail'),
    path('sslcommerz/fail/', views.sslcommerz_fail, name='sslcommerz_fail'),
    path('sslcommerz/cancel/', views.sslcommerz_cancel, name='sslcommerz_cancel'),
    path('sslcommerz/cancel/<int:order_id>/', views.payment_cancel, name='payment_cancel'),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
