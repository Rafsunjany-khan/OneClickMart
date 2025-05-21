from django.contrib.auth.models import User
import requests
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .models import *
from .forms import SignupForm, UserProfileForm
from decimal import Decimal

from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.views import PasswordChangeView
from django.urls import reverse_lazy

from django.http import HttpResponse

def payment_success(request):
    return HttpResponse("Payment successful!")

def payment_fail(request):
    return HttpResponse("Payment failed!")

def payment_cancel(request):
    return HttpResponse("Payment cancelled.")

class CustomPasswordChangeView(PasswordChangeView):
    template_name = 'accounts/change_password.html'  # make sure this template exists
    success_url = reverse_lazy('profile')  # redirect after success
# Home Page
def home(request):
    sliders = Slider.objects.all()
    products = Product.objects.filter(available=True).prefetch_related('images')
    return render(request, 'base.html', {'sliders': sliders, 'products': products})

# Product Detail Page
def product_detail(request, id):
    product = get_object_or_404(Product, id=id)
    return render(request, 'product_detail.html', {'product': product})

# User Signup
def signup(request):
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data['email'],
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
            )
            return redirect('login')
    else:
        form = SignupForm()
    return render(request, 'signup.html', {'form': form})# Login View
def custom_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            return redirect('profile')
        else:
            messages.error(request, "Invalid email or password.")
            return redirect('home')
    return redirect('home')

# Logout View
def user_logout(request):
    logout(request)
    return redirect('home')

# Profile View

@login_required
def profile(request):
    user = request.user
    try:
        profile = user.userprofile
    except UserProfile.DoesNotExist:
        profile = None  # or handle missing profile gracefully

    purchase_history = Order.objects.filter(user=user).order_by('-ordered_at')
    cart_items = CartItem.objects.filter(user=user)

    # Debug print:
    for order in purchase_history:
        print(f"Order ID: {order.id}, Date Ordered: {order.ordered_at}, Total: {order.total_amount}")

    context = {
        'profile': profile,
        'cart_items': cart_items,
        'purchase_history': purchase_history,
        # other context data
    }
    return render(request, 'profile.html', context)

@login_required
def profile_view(request):
    user = request.user
    purchase_history = Order.objects.filter(user=user).order_by('-date_ordered')

    cart_items = CartItem.objects.filter(user=user)  # example for cart items

    profile = user.profile  # or however you get user profile

    context = {
        'purchase_history': purchase_history,
        'cart_items': cart_items,
        'profile': profile,
    }
    return render(request, 'profile.html', context)

# Update Profile View
@login_required
def update_profile(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        profile_form = UserProfileForm(request.POST, request.FILES, instance=profile)
        if profile_form.is_valid():
            profile_form.save()
            messages.success(request, "Profile updated successfully!")
            return redirect('profile')
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        profile_form = UserProfileForm(instance=profile)

    return render(request, 'profile_update.html', {'profile_form': profile_form})

@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # prevent logout
            messages.success(request, 'Password changed successfully!')
            return redirect('login')  # or redirect to profile
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PasswordChangeForm(user=request.user)

    return render(request, 'change_password.html', {'form': form})
# Add to Cart
@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart_item, created = CartItem.objects.get_or_create(user=request.user, product=product)

    if not created:
        cart_item.quantity += 1
        cart_item.save()
        messages.success(request, f"Updated quantity for {product.name} in your cart.")
    else:
        messages.success(request, f"Added {product.name} to your cart.")

    return redirect('cart')

# View Cart
@login_required
def cart_view(request):
    cart_items = CartItem.objects.filter(user=request.user).select_related('product')
    total = sum(item.product.price * item.quantity for item in cart_items)
    return render(request, 'cart.html', {
        'cart_items': cart_items,
        'total': total
    })

# Update Cart
@login_required
def update_cart(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        product_id = request.POST.get('product_id')
        cart_item = CartItem.objects.filter(user=request.user, product_id=product_id).first()

        if cart_item:
            if action == 'add':
                cart_item.quantity += 1
                cart_item.save()
            elif action == 'remove':
                cart_item.quantity -= 1
                if cart_item.quantity <= 0:
                    cart_item.delete()
                else:
                    cart_item.save()
    return redirect('cart')

# Clear Cart
@login_required
def clear_cart(request):
    if request.method == 'POST':
        CartItem.objects.filter(user=request.user).delete()
    return redirect('cart')

# Payment Page
@login_required
def make_payment(request):
    cart_items = CartItem.objects.filter(user=request.user).select_related('product')

    if not cart_items.exists():
        messages.warning(request, "Your cart is empty. Please add products before proceeding.")
        return redirect('cart')

    total = sum(item.product.discount_price * item.quantity for item in cart_items)

    return render(request, 'payment.html', {
        'cart_items': cart_items,
        'total_amount': total
    })

# Place Order
@login_required
def place_order(request):
    user = request.user
    cart_items = CartItem.objects.filter(user=user)

    if not cart_items.exists():
        messages.error(request, "Cart is empty.")
        return redirect('cart')

    order = Order.objects.create(
        user=user,
        total_amount=0,  # Will be updated after calculation
        shipping_address="test address",
        payment_method="Cash"
    )

    total_amount = Decimal('0.00')
    for item in cart_items:
        price = item.product.get_discounted_price()
        subtotal = price * item.quantity
        total_amount += subtotal

        OrderItem.objects.create(
            order=order,
            product=item.product,
            quantity=item.quantity,
            price=price
        )

    order.total_amount = total_amount
    order.save()

    cart_items.delete()
    return redirect('order_success')

# Process Payment View (Cash & SSLCommerz)
@login_required

# Order Success Page
def order_success(request):
    return render(request, 'order_success.html')

import time
# Process Payment (Cash & SSLCommerz)
@login_required
def process_payment(request):
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        total_amount = request.POST.get('total_amount')

        # Validate total_amount
        try:
            total = Decimal(total_amount)
        except (TypeError, ValueError):
            messages.error(request, "Invalid total amount.")
            return redirect('make_payment')

        if payment_method == 'Cash':
            cart_items = CartItem.objects.filter(user=request.user).select_related('product')

            if not cart_items.exists():
                messages.warning(request, "Your cart is empty.")
                return redirect('cart')

            order = Order.objects.create(
                user=request.user,
                total_amount=total,
                payment_method='Cash',
                shipping_address="test address",  # Replace with real address logic
                status='Pending'
            )

            for item in cart_items:
                price = item.product.get_discounted_price()
                subtotal = price * item.quantity

                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price=price
                )

            cart_items.delete()
            messages.success(request, "Payment processed successfully! Your order has been placed.")
            return redirect('order_success')

        elif payment_method == 'SSLCommerz':
            # Prepare SSLCommerz payment data
            payment_data = {
                'store_id': settings.SSLCOMMERZ_STORE_ID,
                'store_passwd': settings.SSLCOMMERZ_STORE_PASSWORD,
                'total_amount': str(total),  # Must be string
                'currency': 'BDT',
                'tran_id': f'TRAN_{request.user.id}_{order.id if "order" in locals() else "NEW"}',  # Unique txn id, improve as needed
                'success_url': request.build_absolute_uri('/payment-success/'),
                'fail_url': request.build_absolute_uri('/payment-fail/'),
                'cancel_url': request.build_absolute_uri('/payment-cancel/'),
                'emi_option': 0,
                'cus_name': request.user.get_full_name() or request.user.username,
                'cus_email': request.user.email,
                'cus_phone': '',  # Add phone if available
                'cus_add1': 'Customer Address',  # You can get real address from user profile
                'cus_city': 'City',
                'cus_postcode': '0000',
                'cus_country': 'Bangladesh',
                'shipping_method': 'NO',
                'product_name': 'Order Payment',
                'product_category': 'General',
                'product_profile': 'general',
            }

            # Call SSLCommerz API
            try:
                response = requests.post(settings.SSLCOMMERZ_API_SESSION_URL, data=payment_data)
                response_data = response.json()
            except Exception as e:
                messages.error(request, f"Failed to initiate payment: {str(e)}")
                return redirect('make_payment')

            if response_data.get('status') == 'SUCCESS':
                # Redirect user to SSLCommerz payment page
                return redirect(response_data['GatewayPageURL'])
            else:
                messages.error(request, "Payment initiation failed. Please try again.")
                return redirect('make_payment')

        else:
            messages.error(request, "Invalid payment method selected.")
            return redirect('make_payment')

    return redirect('cart')
# Initiate SSLCommerz Payment
@login_required
def initiate_payment(request):
    if request.method == "POST":
        payment_data = {
            'store_id': settings.SSLCOMMERZ_STORE_ID,
            'store_passwd': settings.SSLCOMMERZ_STORE_PASSWORD,
            'total_amount': 100,  # Change as needed
            'currency': 'BDT',
            'tran_id': 'TEST12345',  # Generate unique ID in production
            'success_url': 'http://127.0.0.1:8000/payment-success/',
            'fail_url': 'http://127.0.0.1:8000/payment-fail/',
            'cancel_url': 'http://127.0.0.1:8000/payment-cancel/',
            'emi_option': 0,
            'cus_name': 'Test User',
            'cus_email': 'test@example.com',
            'cus_phone': '01700000000',
            'cus_add1': 'Dhaka',
            'cus_city': 'Dhaka',
            'cus_postcode': '1200',
            'cus_country': 'Bangladesh',
            'shipping_method': 'NO',
            'product_name': 'Test Product',
            'product_category': 'Electronic',
            'product_profile': 'general',
        }

        response = requests.post(settings.SSLCOMMERZ_API_SESSION_URL, data=payment_data)
        response_data = response.json()

        if response_data.get('status') == 'SUCCESS':
            return redirect(response_data['GatewayPageURL'])
        else:
            messages.error(request, "Payment initiation failed.")
            return redirect('make_payment')  # Your payment form view
    else:
        return redirect('make_payment')

def order_success(request):
    return render(request, 'order_success.html')
