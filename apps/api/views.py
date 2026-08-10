from django.shortcuts import render

def dashboard_view(request):
    return render(request, 'dashboard.html')

def websites_view(request):
    return render(request, 'websites.html')