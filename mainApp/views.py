from django.contrib.auth.models import User
import requests
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib import messages
from .models import *
from .forms import SignupForm, UserProfileForm
from decimal import Decimal
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

# Payment Result Views
def payment_success(request):
    return HttpResponse("Payment successful!")

def payment_fail(request):
    return HttpResponse("Payment failed!")

def payment_cancel(request):
    return HttpResponse("Payment cancelled.")

# Password Change View
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
                is_active=False  # User inactive until email verified
            )
            user.save()

            # Instead of getting current_site from request, set domain manually for local testing
            domain = 'localhost:8000'  # Your local server and port

            mail_subject = 'Activate your account'
            message = render_to_string('acc_activate_email.html', {
                'user': user,
                'domain': domain,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': default_token_generator.make_token(user),
            })
            to_email = form.cleaned_data.get('email')
            email = EmailMessage(mail_subject, message, to=[to_email])
            email.send()

            return render(request, 'activation_sent.html')
    else:
        form = SignupForm()
    return render(request, 'signup.html', {'form': form})
# Email Activation code
def activate(request, uidb64, token):
    try:
        # Decode the user id from the base64 string
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True  # Activate the user
        user.save()
        login(request, user)  # Automatically login after activation
        return redirect('profile')  # Redirect to profile or homepage
    else:
        return render(request, 'activation_invalid.html')# Login View

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
            return redirect('login')  # redirect back to login on error
    return render(request, 'login.html')  # Corrected path to your template
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
        profile = None

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

    return render(request, 'payment.html', {'cart_items': cart_items, 'total_amount': total})

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
        total_amount=0,
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

@login_required
def place_order_view(request):
    if request.method == "POST":
        payment_method = request.POST.get('payment_method')  # 'Cash' or 'SSLCommerz'

        if payment_method != "Cash":
            messages.error(request, "Only Cash payment is supported right now.")
            return redirect('checkout')

        cart_items = CartItem.objects.filter(user=request.user)
        if not cart_items.exists():
            messages.warning(request, "Your cart is empty.")
            return redirect('cart')

        # Create Order
        order = Order.objects.create(
            user=request.user,
            total_amount=sum(item.product.price * item.quantity for item in cart_items),
            payment_method="Cash",
            status="Pending",
            created_at=timezone.now()
        )

        # Create Order Items
        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                price=item.product.price
            )

        # Clear user's cart
        cart_items.delete()

        messages.success(request, "Order placed successfully with Cash payment.")
        return redirect('order_success')

    return redirect('checkout')

# Order Success
@login_required
def order_success(request):
    return render(request, 'order_success.html')

# Process Payment (Cash & SSLCommerz)
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

        order = Order.objects.create(
            user=request.user,
            total_amount=total,
            payment_method=payment_method,
            shipping_address="test address",
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
            cart_items.delete()
            messages.success(request, "Payment processed successfully! Your order has been placed.")
            return redirect('order_success')

        elif payment_method == 'SSLCommerz':
            payment_data = {
                'store_id': settings.SSLCOMMERZ_STORE_ID,
                'store_passwd': settings.SSLCOMMERZ_STORE_PASSWORD,
                'total_amount': str(total),
                'currency': 'BDT',
                'tran_id': f'TRAN_{request.user.id}_{order.id}',
                'success_url': request.build_absolute_uri('/payment-success/'),
                'fail_url': request.build_absolute_uri('/payment-fail/'),
                'cancel_url': request.build_absolute_uri('/payment-cancel/'),
                'emi_option': 0,
                'cus_name': request.user.get_full_name() or request.user.username,
                'cus_email': request.user.email,
                'cus_phone': '',
                'cus_add1': 'Customer Address',
                'cus_city': 'City',
                'cus_postcode': '0000',
                'cus_country': 'Bangladesh',
                'shipping_method': 'NO',
                'product_name': 'Order Payment',
                'product_category': 'General',
                'product_profile': 'general',
            }

            try:
                response = requests.post(settings.SSLCOMMERZ_API_SESSION_URL, data=payment_data)
                response_data = response.json()
            except Exception as e:
                messages.error(request, f"Failed to initiate payment: {str(e)}")
                return redirect('make_payment')

            if response_data.get('status') == 'SUCCESS':
                cart_items.delete()
                return redirect(response_data['GatewayPageURL'])
            else:
                messages.error(request, "Payment initiation failed. Please try again.")
                return redirect('make_payment')

        else:
            messages.error(request, "Invalid payment method selected.")
            return redirect('make_payment')

    return redirect('cart')

# Initiate SSLCommerz Payment (for testing)
@login_required
def initiate_payment(request):
    if request.method == "POST":
        payment_data = {
            'store_id': settings.SSLCOMMERZ_STORE_ID,
            'store_passwd': settings.SSLCOMMERZ_STORE_PASSWORD,
            'total_amount': 100,
            'currency': 'BDT',
            'tran_id': 'TEST12345',
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
            return HttpResponse("Payment initiation failed")
    return render(request, 'initiate_payment.html')

# SSLCommerz Payment Success Webhook
@csrf_exempt
def sslcommerz_payment_success(request):
    if request.method == 'POST':
        tran_id = request.POST.get('tran_id')
        val_id = request.POST.get('val_id')
        amount = request.POST.get('amount')
        card_type = request.POST.get('card_type')
        bank_tran_id = request.POST.get('bank_tran_id')
        currency = request.POST.get('currency')
        store_amount = request.POST.get('store_amount')
        status = request.POST.get('status')
        tran_date = request.POST.get('tran_date')
        card_no = request.POST.get('card_no')
        currency_type = request.POST.get('currency_type')
        verify_sign = request.POST.get('verify_sign')

        try:
            order = Order.objects.get(tran_id=tran_id)
        except Order.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Order not found'}, status=404)

        payment, created = Payment.objects.get_or_create(order=order)
        payment.payment_status = status
        payment.payment_date = tran_date
        payment.bank_transaction_id = bank_tran_id
        payment.card_type = card_type
        payment.card_no = card_no
        payment.amount = Decimal(amount)
        payment.currency = currency
        payment.val_id = val_id
        payment.verify_sign = verify_sign
        payment.save()

        order.status = 'Paid' if status == 'VALID' else 'Failed'
        order.save()

        return JsonResponse({'status': 'success', 'message': 'Payment recorded successfully'})
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)
