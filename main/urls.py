
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('strategy/<int:situation_id>/', views.strategy, name='strategy'),
    path('steps/<int:strategy_id>/', views.steps_view, name='steps'),
]
