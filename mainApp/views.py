from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .models import UserProfile, Slider, Product, CartItem

# Home Page
def home(request):
    sliders = Slider.objects.all()
    products = Product.objects.filter(available=True).prefetch_related('images')
    return render(request, 'base.html', {'sliders': sliders, 'products': products})

# User Signup
def signup(request):
    if request.method == 'POST':
        fname = request.POST['first_name']
        lname = request.POST['last_name']
        email = request.POST['email']
        password = request.POST['password']
        confirm = request.POST['confirm_password']

        if password == confirm:
            user = User.objects.create_user(username=email, email=email, password=password)
            user.first_name = fname
            user.last_name = lname
            user.save()
            return redirect('login')
    return render(request, 'signup.html')

# Login View
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

# Profile View
@login_required
def profile(request):
    user = request.user
    profile, created = UserProfile.objects.get_or_create(user=user)

    if request.method == 'POST':
        profile.profile_image = request.FILES.get('profile_image')
        profile.address_line_1 = request.POST.get('address_line_1')
        profile.address_line_2 = request.POST.get('address_line_2')
        profile.phone_number = request.POST.get('phone_number')
        profile.city = request.POST.get('city')
        profile.postcode = request.POST.get('postcode')
        profile.save()
        return redirect('profile')

    return render(request, 'profile.html', {'profile': profile})

# Logout
def user_logout(request):
    logout(request)
    return redirect('home')

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

# View Cart (Model-Based)
@login_required
def cart_view(request):
    cart_items = CartItem.objects.filter(user=request.user).select_related('product')
    total = sum(item.product.price * item.quantity for item in cart_items)

    return render(request, 'cart.html', {
        'cart_items': cart_items,
        'total': total
    })

# Update Cart (Increase or Decrease)
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

def make_payment(request):
    return render(request, 'payment.html')
