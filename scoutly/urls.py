from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path


def raiz_view(request):
    return redirect("dashboard" if request.user.is_authenticated else "login")


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', raiz_view, name='raiz'),
    path('', include('accounts.urls')),
    path('', include('vacantes.urls')),
]
