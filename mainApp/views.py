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
from django.urls import reverse_lazy, reverse

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMessage

from .utils import generate_otp, send_otp_via_email

import uuid

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

    # Get or create the cart item
    cart_item, created = CartItem.objects.get_or_create(
        user=request.user,
        product=product,
        defaults={'quantity': 1}
    )
    if not created:
        cart_item.quantity += 1
        cart_item.save()

    messages.success(request, f"{product.name} added to cart.")
    return redirect('cart')


# View Cart
@login_required
def cart_view(request):
    try:
        order = Order.objects.get(user=request.user, status='Pending')
        cart_items = order.items.select_related('product')
        total = sum(item.product.price * item.quantity for item in cart_items)
    except Order.DoesNotExist:
        cart_items = []
        total = 0

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
    try:
        order = Order.objects.get(user=request.user, status='Pending')
    except Order.DoesNotExist:
        messages.warning(request, "Your cart is empty or no pending order found.")
        return redirect('cart')

    order_items = order.items.select_related('product')

    if not order_items.exists():
        messages.warning(request, "Your cart is empty. Please add products before proceeding.")
        return redirect('cart')

    total = sum(item.product.price * item.quantity for item in order_items)

    return render(request, 'payment.html', {
        'cart_items': order_items,
        'total_amount': total,
        'order': order,
    })
# Order Success Page
@login_required
def order_success(request):
    return render(request, 'order_success.html')

def update_stock(order):
    for item in order.items.all():
        product = item.product
        # reduce stock only if available
        if product.stock >= item.quantity:
            product.stock -= item.quantity
            product.save()
        else:
            # Handle out of stock scenario if needed
            pass



def some_sslcommerz_api_call(data):
    sslcommerz_url = "https://sandbox.sslcommerz.com/gwprocess/v4/api.php"  # Sandbox URL, use live URL for production

    # Include mandatory store credentials from settings
    payload = {
        'store_id': settings.SSLCOMMERZ_STORE_ID,
        'store_passwd': settings.SSLCOMMERZ_STORE_PASSWORD,
        **data
    }

    try:
        response = requests.post(sslcommerz_url, data=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        # You can log the exception here for debugging
        return {'status': 'FAILED', 'error': str(e)}


@login_required
def process_payment(request):
    if request.method == "POST":
        user = request.user
        payment_method = request.POST.get('payment_method')
        total_amount = request.POST.get('total_amount')

        # Create the order
        order = Order.objects.create(
            user=user,
            total_amount=total_amount,
            payment_method=payment_method,
            status='Pending',
            # You can add shipping_address from user profile or form here
        )

        if payment_method == 'Cash':
            # Handle cash payment logic here (e.g., mark order as Pending)
            return redirect('order_success')  # or your success page

        elif payment_method == 'SSLCommerz':
            # Prepare payload for SSLCommerz
            payload = {
                'store_id': settings.SSLCOMMERZ_STORE_ID,
                'store_passwd': settings.SSLCOMMERZ_STORE_PASSWORD,
                'total_amount': str(total_amount),
                'currency': 'BDT',
                'tran_id': f"order-{order.id}-{uuid.uuid4()}",
                'success_url': request.build_absolute_uri(reverse('payment_success', kwargs={'order_id': order.id})),
                'fail_url': request.build_absolute_uri(reverse('payment_fail', kwargs={'order_id': order.id})),
                'cancel_url': request.build_absolute_uri(reverse('payment_cancel', kwargs={'order_id': order.id})),
                'cus_name': user.get_full_name() or user.username,
                'cus_email': user.email,
                'cus_add1': order.shipping_address or '',
                'cus_city': 'Dhaka',
                'cus_state': '',
                'cus_postcode': '',
                'cus_country': 'Bangladesh',
                'cus_phone': '01701983377',
                'shipping_method': 'NO',
                'product_name': 'Samsung Galaxy S24 Ultra 5G',
                'product_category': 'Electronic',
                'product_profile': 'physical-goods',  # <--- Add this field!
                'num_of_item': 1,
            }

            # Call SSLCommerz API
            response = requests.post(
                'https://sandbox.sslcommerz.com/gwprocess/v4/api.php',
                data=payload
            )

            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'SUCCESS':
                    gateway_url = result.get('GatewayPageURL')
                    if gateway_url:
                        return redirect(gateway_url)
                    else:
                        # Handle missing GatewayPageURL
                        messages.error(request, "SSLCommerz response missing GatewayPageURL.")
                else:
                    # Handle failure status from SSLCommerz
                    error_msg = result.get('failedreason') or 'SSLCommerz payment initiation failed.'
                    messages.error(request, error_msg)
            else:
                messages.error(request, "Failed to connect to SSLCommerz API.")

            # Redirect back to payment page on failure
            return redirect('make_payment')

    # For GET or other methods, you can redirect or render as needed
    return redirect('cart')  # Or wherever appropriate

@csrf_exempt
def sslcommerz_payment_success(request,order_id):
    if request.method == 'POST':
        tran_id = request.POST.get('tran_id')
        val_id = request.POST.get('val_id')
        status = request.POST.get('status')
        amount = request.POST.get('amount')

        if not all([tran_id, val_id, status, amount]):
            return HttpResponse("Missing parameters", status=400)

        if status == 'VALID':
            try:
                order = Order.objects.get(transaction_id=tran_id)
            except Order.DoesNotExist:
                return HttpResponse("Order not found", status=404)

            order.status = 'Completed'
            order.save()

            Payment.objects.create(
                order=order,
                transaction_id=tran_id,
                payment_method='SSLCommerz',
                amount=Decimal(amount),
                status='Completed'
            )

            update_stock(order)
            CartItem.objects.filter(user=order.user).delete()

            return HttpResponse("Payment completed successfully")
        else:
            return HttpResponse("Payment not valid", status=400)
    return HttpResponse("Invalid method", status=405)



def calculate_cart_total(user):
    items = CartItem.objects.filter(user=user)
    return sum(item.product.price * item.quantity for item in items)

def initiate_sslcommerz_payment(request):
    if request.method == 'POST':
        user = request.user
        address = request.POST.get('shipping_address')  # Or use user.profile.address if stored

        # Step 1: Calculate total and generate unique transaction ID
        total_amount = calculate_cart_total(user)
        transaction_id = uuid.uuid4().hex

        # Step 2: Save order in DB with status 'Pending'
        order = Order.objects.create(
            user=user,
            total_amount=Decimal(total_amount),
            shipping_address=address,
            payment_method='SSLCommerz',
            transaction_id=transaction_id
        )

        # Step 3: Prepare SSLCommerz payload
        payload = {
            'store_id': settings.SSLCOMMERZ_STORE_ID,
            'store_passwd': settings.SSLCOMMERZ_STORE_PASSWORD,
            'total_amount': float(total_amount),
            'currency': 'BDT',
            'tran_id': transaction_id,
            'success_url': request.build_absolute_uri(reverse('sslcommerz_success')),
            'fail_url': request.build_absolute_uri(reverse('sslcommerz_fail')),
            'cancel_url': request.build_absolute_uri(reverse('sslcommerz_cancel')),

            'cus_name': user.get_full_name() or 'Customer',
            'cus_email': user.email or 'customer@example.com',
            'cus_add1': address or 'Address not provided',
            'cus_city': 'Dhaka',
            'cus_postcode': '1207',
            'cus_country': 'Bangladesh',
            'cus_phone': '01701983377',

            'product_category': 'Electronic',
            'product_name': 'Cart Products',
            'product_profile': 'physical-goods',
        }

        # Step 4: Send request to SSLCommerz
        response = requests.post('https://sandbox.sslcommerz.com/gwprocess/v4/api.php', data=payload)
        data = response.json()

        if data.get('status') == 'SUCCESS':
            return redirect(data['GatewayPageURL'])  # Redirect user to payment page
        else:
            return HttpResponse("SSLCommerz payment initiation failed", status=500)

    return HttpResponse("Invalid request method", status=405)

@login_required
def payment_success(request, order_id):
    try:
        order = Order.objects.get(id=order_id, user=request.user)
    except Order.DoesNotExist:
        messages.error(request, "Order not found")
        return redirect('cart')

    # You don't need to call get_object_or_404 again, you already have order
    # order = get_object_or_404(Order, id=order_id, user=request.user) <-- remove this

    order.status = 'Completed'
    order.save()

    update_stock(order)
    CartItem.objects.filter(user=request.user).delete()
    messages.success(request, "Payment successful!")
    return redirect('order_success')


@login_required
def payment_fail(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    order.status = 'Failed'
    order.save()
    messages.error(request, "Payment failed.")
    return redirect('make_payment')

@login_required
def payment_cancel(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    order.status = 'Cancelled'
    order.save()
    messages.warning(request, "Payment cancelled.")
    return redirect('cart')



import requests

def sslcommerz_api_call(payload):
    sslcommerz_init_url = 'https://sandbox.sslcommerz.com/gwprocess/v4/api.php'  # Use production URL if live
    response = requests.post(sslcommerz_init_url, data=payload)
    if response.status_code == 200:
        return response.json()
    else:
        return {'status': 'FAILED'}
