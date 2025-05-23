from django.contrib.auth.models import User
import requests
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib import messages
from .models import *
from .forms import SignupForm, UserProfileForm, OTPForm
from decimal import Decimal
from django.db import transaction
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import PasswordChangeView
from django.urls import reverse_lazy
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMessage

from .utils import generate_otp, send_otp_via_email

# Payment Result Views
def payment_success(request):
    return HttpResponse("Payment successful!")

def payment_fail(request):
    return HttpResponse("Payment failed!")

def payment_cancel(request):
    return HttpResponse("Payment cancelled.")

# Password Change View (class-based)
class CustomPasswordChangeView(PasswordChangeView):
    template_name = 'accounts/change_password.html'
    success_url = reverse_lazy('profile')

# Home Page
def home(request):
    sliders = Slider.objects.all()
    products = Product.objects.filter(available=True).order_by('-created_at').prefetch_related('images')
    return render(request, 'base.html', {'sliders': sliders, 'products': products})

def product_list(request):
    products = Product.objects.filter(available=True).order_by('-created_at').prefetch_related('images')
    return render(request, 'products.html', {'products': products})

# Product Detail Page
def product_detail(request, id):
    product = get_object_or_404(Product, id=id)
    return render(request, 'product_detail.html', {'product': product})

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
                is_active=False
            )
            user.save()

            otp = generate_otp()
            request.session['otp'] = otp
            request.session['user_id'] = user.id

            send_otp_via_email(user.email, otp)

            return redirect('verify_otp')  # Redirect to OTP form page
    else:
        form = SignupForm()
    return render(request, 'signup.html', {'form': form})

from django.contrib.auth.hashers import make_password

from django.contrib.auth import get_backends

def verify_otp_view(request):
    if request.method == 'POST':
        input_otp = request.POST.get('otp')
        session_otp = request.session.get('otp')
        user_id = request.session.get('user_id')

        if input_otp == session_otp and user_id:
            user = User.objects.get(id=user_id)
            user.is_active = True
            user.save()

            # Specify backend manually
            backend = get_backends()[0]
            user.backend = f"{backend.__module__}.{backend.__class__.__name__}"
            login(request, user)

            # Clean session data
            request.session.pop('otp')
            request.session.pop('user_id')

            messages.success(request, 'OTP verified! You are now logged in.')
            return redirect('home')
        else:
            messages.error(request, 'Invalid OTP, please try again.')

    return render(request, 'verify_otp.html')

def activate(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        login(request, user)
        return redirect('profile')
    else:
        return render(request, 'activation_invalid.html')

# Login View
def custom_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, username=email, password=password)
        if user:
            login(request, user)
            return redirect('profile')
        else:
            messages.error(request, "Invalid email or password.")
            return redirect('login')
    return render(request, 'login.html')

# Logout View
def user_logout(request):
    logout(request)
    return redirect('home')

# Profile View
@login_required
def profile(request):
    user = request.user
    profile = getattr(user, 'userprofile', None)

    purchase_history = Order.objects.filter(user=user).order_by('-ordered_at')
    cart_items = CartItem.objects.filter(user=user)

    context = {
        'profile': profile,
        'cart_items': cart_items,
        'purchase_history': purchase_history,
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

# Change Password View
@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Password changed successfully!')
            return redirect('profile')
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
    return render(request, 'cart.html', {'cart_items': cart_items, 'total': total})

# Update Cart Item Quantity
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

# Checkout Page
@login_required
def checkout_view(request):
    cart_items = CartItem.objects.filter(user=request.user)
    if not cart_items.exists():
        messages.warning(request, "Your cart is empty.")
        return redirect('cart')

    total_price = sum(item.product.price * item.quantity for item in cart_items)

    return render(request, 'checkout.html', {
        'cart_items': cart_items,
        'total_price': total_price,
    })

# Payment Page (Choose Payment Method)
@login_required
def make_payment(request):
    cart_items = CartItem.objects.filter(user=request.user).select_related('product')

    if not cart_items.exists():
        messages.warning(request, "Your cart is empty. Please add products before proceeding.")
        return redirect('cart')

    total = sum(item.product.discount_price * item.quantity for item in cart_items)

    return render(request, 'payment.html', {'cart_items': cart_items, 'total_amount': total})

# Process Payment (Cash or SSLCommerz)
@login_required
def process_payment(request):
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        total_amount = request.POST.get('total_amount')

        try:
            total = Decimal(total_amount)
        except (TypeError, ValueError):
            messages.error(request, "Invalid total amount.")
            return redirect('make_payment')

        cart_items = CartItem.objects.filter(user=request.user).select_related('product')
        if not cart_items.exists():
            messages.warning(request, "Your cart is empty.")
            return redirect('cart')

        # Create order with Pending status
        order = Order.objects.create(
            user=request.user,
            total_amount=total,
            payment_method=payment_method,
            shipping_address="test address",  # Change as per your form/input
            status='Pending'
        )

        for item in cart_items:
            price = item.product.get_discounted_price()
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                price=price
            )

        if payment_method == 'Cash':
            Payment.objects.create(
                order=order,
                transaction_id=f"CASH-{order.id}",
                payment_method='Cash',
                amount=total,
                status='Completed'
            )
            cart_items.delete()
            messages.success(request, "Order placed successfully with Cash payment.")
            return redirect('order_success')

        elif payment_method == 'SSLCommerz':
            # Prepare SSLCommerz payment request here
            sslcommerz_api = "https://sandbox.sslcommerz.com/gwprocess/v4/api.php"

            payload = {
                'store_id': settings.SSLCOMMERZ_STORE_ID,
                'store_passwd': settings.SSLCOMMERZ_STORE_PASSWORD,
                'total_amount': str(total),
                'currency': 'BDT',
                'tran_id': str(order.id),
                'success_url': request.build_absolute_uri(reverse_lazy('sslcommerz_payment_success')),
                'fail_url': request.build_absolute_uri(reverse_lazy('payment_fail')),
                'cancel_url': request.build_absolute_uri(reverse_lazy('payment_cancel')),
                'cus_name': request.user.get_full_name(),
                'cus_email': request.user.email,
                'cus_add1': order.shipping_address,
                'cus_phone': '017XXXXXXXX',
                'shipping_method': 'NO',
                'product_name': ', '.join([item.product.name for item in cart_items]),
                'num_of_item': cart_items.count(),
            }

            response = requests.post(sslcommerz_api, data=payload)
            sslcommerz_response = response.json()

            if sslcommerz_response.get('status') == 'SUCCESS':
                payment_url = sslcommerz_response.get('GatewayPageURL')
                return redirect(payment_url)
            else:
                messages.error(request, "SSLCommerz payment initiation failed. Please try again.")
                return redirect('make_payment')

        else:
            messages.error(request, "Invalid payment method selected.")
            return redirect('make_payment')

    return redirect('make_payment')

# SSLCommerz Payment Success Callback
@csrf_exempt
def sslcommerz_payment_success(request):
    if request.method == 'POST':
        tran_id = request.POST.get('tran_id')
        val_id = request.POST.get('val_id')
        status = request.POST.get('status')
        amount = request.POST.get('amount')

        # TODO: Validate the payment using hash/signature verification here

        try:
            order = Order.objects.get(id=tran_id)
            payment = Payment.objects.get(order=order)
        except (Order.DoesNotExist, Payment.DoesNotExist):
            return HttpResponse("Invalid transaction", status=400)

        if status in ('VALID', 'SUCCESS'):
            payment.status = 'Completed'
            order.status = 'Completed'
        else:
            payment.status = 'Failed'
            order.status = 'Failed'

        payment.save()
        order.save()

        if status in ('VALID', 'SUCCESS'):
            # Clear cart
            CartItem.objects.filter(user=order.user).delete()
            messages.success(request, "Payment verified successfully!")
            return redirect('order_success')
        else:
            messages.error(request, "Payment failed or cancelled.")
            return redirect('payment_fail')

    return HttpResponse("Invalid request method.", status=405)

# Order Success Page
@login_required
def order_success(request):
    return render(request, 'order_success.html')
