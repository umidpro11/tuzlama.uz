from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('cart/', views.cart_api_view, name='cart_api'),
    path('cart/update/', views.cart_update_view, name='cart_update'),
    path('favorites/toggle/', views.toggle_favorite_view, name='toggle_favorite'),
    path('products/<int:produkt_id>/reviews/', views.product_reviews_view, name='product_reviews'),
    path('products/<int:produkt_id>/review/', views.add_product_review_view, name='add_product_review'),
    path('contact/submit/', views.submit_contact_view, name='submit_contact'),
    path('orders/', views.orders_view, name='orders'),
    path('orders/estimate/', views.estimate_delivery_view, name='estimate_delivery'),
    path('orders/create/', views.create_order_view, name='create_order'),
    path('orders/<int:order_id>/delivery/', views.update_order_delivery_view, name='update_order_delivery'),
    path('orders/<int:order_id>/location/', views.update_my_order_location_view, name='update_my_order_location'),
    path('orders/poll/', views.orders_poll_view, name='orders_poll'),
]
