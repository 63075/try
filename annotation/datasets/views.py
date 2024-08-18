from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Dataset, Image, Annotation
from .forms import DatasetForm, ImageForm
from PIL import Image
import numpy as np
from PIL import cv2
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.conf import settings
from PIL import Image as PILImage, ImageDraw, ImageFont
import os

@login_required
def create_dataset(request):
    if request.method == 'POST':
        form = DatasetForm(request.POST)
        if form.is_valid():
            dataset = form.save(commit=False)
            dataset.owner = request.user
            dataset.save()
            return redirect('dataset_detail', pk=dataset.pk)
    else:
        form = DatasetForm()
    return render(request, 'datasets/create_dataset.html', {'form': form})

@login_required
def upload_image(request, pk):
    dataset = Dataset.objects.get(pk=pk)
    if request.method == 'POST':
        form = ImageForm(request.POST, request.FILES)
        if form.is_valid():
            image = form.save(commit=False)
            image.dataset = dataset
            image.save()
            return redirect('dataset_detail', pk=dataset.pk)
    else:
        form = ImageForm()
    return render(request, 'datasets/upload_image.html', {'form': form})

@login_required
def dataset_detail(request, pk):
    dataset = Dataset.objects.get(pk=pk)
    images = Image.objects.filter(dataset=dataset)
    return render(request, 'datasets/dataset_detail.html', {'dataset': dataset, 'images': images})

def load_yolo():
    net = cv2.dnn.readNet("yolov3.weights", "yolov3.cfg")
    with open("coco.names", "r") as f:
        classes = [line.strip() for line in f.readlines()]
    layer_names = net.getLayerNames()
    output_layers = [layer_names[i[0] - 1] for i in net.getUnconnectedOutLayers()]
    return net, classes, output_layers

def detect_objects(img, net, output_layers):
    height, width, channels = img.shape
    blob = cv2.dnn.blobFromImage(img, 0.00392, (416, 416), (0, 0, 0), True, crop=False)
    net.setInput(blob)
    outs = net.forward(output_layers)
    
    # Information to return
    class_ids = []
    confidences = []
    boxes = []

    for out in outs:
        for detection in out:
            scores = detection[5:]
            class_id = np.argmax(scores)
            confidence = scores[class_id]
            if confidence > 0.5:
                # Object detected
                center_x = int(detection[0] * width)
                center_y = int(detection[1] * height)
                w = int(detection[2] * width)
                h = int(detection[3] * height)
                
                # Rectangle coordinates
                x = int(center_x - w / 2)
                y = int(center_y - h / 2)
                
                boxes.append([x, y, w, h])
                confidences.append(float(confidence))
                class_ids.append(class_id)
        return class_ids, confidences, boxes
    
def generate_annotations(request, pk):
    image = Image.objects.get(pk=pk)
    img = cv2.imread(image.image.path)
    net, classes, output_layers = load_yolo()
    
    class_ids, confidences, boxes = detect_objects(img, net, output_layers)

    for i in range(len(boxes)):
        x, y, w, h = boxes[i]
        label = str(classes[class_ids[i]])
        Annotation.objects.create(
            image=image,
            label=label,
            x=x,
            y=y,
            width=w,
            height=h
        )    
    return render(request, 'datasets/annotation_results.html', {'image': image, 'annotations': Annotation.objects.filter(image=image)})

@login_required
def save_annotated_image(request, image_id):
    image_instance = get_object_or_404(Image, id=image_id)
    annotations = Annotation.objects.filter(image=image_instance)

    # Open the original image using Pillow
    img_path = os.path.join(settings.MEDIA_ROOT, image_instance.image.name)
    img = PILImage.open(img_path)
    draw = ImageDraw.Draw(img)

    # Draw each annotation on the image
    for annotation in annotations:
        x1, y1 = annotation.x, annotation.y
        x2, y2 = x1 + annotation.width, y1 + annotation.height
        draw.rectangle([x1, y1, x2, y2], outline="red", width=2)

        # Optional: Draw label text above the rectangle
        font = ImageFont.load_default()
        text_position = (x1, y1 - 10)
        draw.text(text_position, annotation.label, fill="red", font=font)

     # Save the annotated image
    annotated_image_path = os.path.join(settings.MEDIA_ROOT, 'annotated', f"annotated_{image_instance.image.name}")
    os.makedirs(os.path.dirname(annotated_image_path), exist_ok=True)
    img.save(annotated_image_path)

    # Serve the image as a response (or redirect to a success page)
    with open(annotated_image_path, "rb") as f:
        return HttpResponse(f.read(), content_type="image/png")