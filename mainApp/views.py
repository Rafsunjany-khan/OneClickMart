from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .models import *
from .forms import SignupForm, UserProfileForm
from decimal import Decimal

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
def process_payment(request):
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')

        if payment_method == 'Cash':
            cart_items = CartItem.objects.filter(user=request.user).select_related('product')

            if not cart_items.exists():
                messages.warning(request, "Your cart is empty.")
                return redirect('cart')

            total = Decimal('0.00')
            order = Order.objects.create(
                user=request.user,
                total_amount=0,
                payment_method='Cash',
                shipping_address="test address",
                status='Pending'
            )

            for item in cart_items:
                price = item.product.get_discounted_price()
                subtotal = price * item.quantity
                total += subtotal

                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price=price
                )

            order.total_amount = total
            order.save()

            cart_items.delete()
            messages.success(request, "Payment processed successfully! Your order has been placed.")
            return redirect('order_success')

        elif payment_method == 'SSLCommerz':
            messages.warning(request, "SSLCommerz payment method is under development.")
            return redirect('make_payment')

    return redirect('cart')

# Order Success Page
def order_success(request):
    return render(request, 'order_success.html')
