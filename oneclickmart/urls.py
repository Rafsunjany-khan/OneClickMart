from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('auth/', include("authentications.urls")),
    path('admin/', admin.site.urls),
    path("", include("mainApp.urls")),
]
