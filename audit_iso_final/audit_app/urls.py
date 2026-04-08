from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Auth
    path('', views.home, name='home'),
    path('login/', auth_views.LoginView.as_view(template_name='audit_app/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', views.register, name='register'),

    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),

    # Scenarios list & start
    path('scenarios/', views.scenario_list, name='scenario_list'),
    path('scenarios/<int:scenario_id>/start/', views.start_audit, name='start_audit'),

    # Scenario management (create/edit)
    path('scenarios/create/', views.scenario_create, name='scenario_create'),
    path('scenarios/<int:scenario_id>/edit/', views.scenario_edit, name='scenario_edit'),
    path('scenarios/<int:scenario_id>/delete/', views.scenario_delete, name='scenario_delete'),
    path('scenarios/<int:scenario_id>/controls/', views.scenario_add_controls, name='scenario_add_controls'),
    path('scenarios/<int:scenario_id>/controls/<int:sc_id>/delete/', views.scenario_control_delete, name='scenario_control_delete'),
    path('scenarios/<int:scenario_id>/controls/<int:sc_id>/evidences/', views.scenario_add_evidences, name='scenario_add_evidences'),
    path('scenarios/<int:scenario_id>/controls/<int:sc_id>/evidences/<int:ev_id>/delete/', views.evidence_delete, name='evidence_delete'),

    # Audit session
    path('audit/<int:session_id>/', views.audit_overview, name='audit_overview'),
    path('audit/<int:session_id>/control/<int:sc_id>/', views.audit_control, name='audit_control'),
    path('audit/<int:session_id>/control/<int:sc_id>/evidence/<int:ev_id>/', views.get_evidence, name='get_evidence'),
    path('audit/<int:session_id>/control/<int:sc_id>/evaluate/', views.evaluate_control, name='evaluate_control'),
    path('audit/<int:session_id>/complete/', views.complete_audit, name='complete_audit'),
    path('audit/<int:session_id>/report/', views.audit_report, name='audit_report'),
    path('audit/<int:session_id>/report/pdf/', views.audit_report_pdf, name='audit_report_pdf'),

    # APIs
    path('api/session/<int:session_id>/progress/', views.api_session_progress, name='api_progress'),
    path('api/controls/', views.api_controls_list, name='api_controls_list'),
]
