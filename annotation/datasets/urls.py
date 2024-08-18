from django.urls import path
from . import views

urlpatterns = [
    path('create/', views.create_dataset, name='create_dataset'),
    path('<int:pk>/', views.dataset_detail, name='dataset_detail'),
    path('<int:pk>/upload/', views.upload_image, name='upload_image'),
    path('<int:image_id>/save_annotated_image/', views.save_annotated_image, name='save_annotated_image'),
]