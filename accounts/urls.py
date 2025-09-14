from django.urls import path
from .views import google_start, post_login_redirect

urlpatterns = [
    path("google/start/", google_start, name="google_start"),
    path("post-login/", post_login_redirect, name="post_login"),
]