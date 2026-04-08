from django.contrib import admin
from .models import (
    Scenario, ISOControl, ScenarioControl, Evidence,
    AuditSession, ControlEvaluation
)


class EvidenceInline(admin.TabularInline):
    model = Evidence
    extra = 1


class ScenarioControlInline(admin.TabularInline):
    model = ScenarioControl
    extra = 1


@admin.register(Scenario)
class ScenarioAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'sector', 'difficulty', 'is_active']
    list_filter = ['sector', 'difficulty', 'is_active']
    inlines = [ScenarioControlInline]


@admin.register(ISOControl)
class ISOControlAdmin(admin.ModelAdmin):
    list_display = ['code', 'norm', 'category', 'title']
    list_filter = ['norm', 'category']
    search_fields = ['code', 'title']


@admin.register(ScenarioControl)
class ScenarioControlAdmin(admin.ModelAdmin):
    list_display = ['scenario', 'control', 'order']
    list_filter = ['scenario']
    inlines = [EvidenceInline]


@admin.register(AuditSession)
class AuditSessionAdmin(admin.ModelAdmin):
    list_display = ['user', 'scenario', 'status', 'score', 'max_score', 'started_at']
    list_filter = ['status', 'scenario']


@admin.register(ControlEvaluation)
class ControlEvaluationAdmin(admin.ModelAdmin):
    list_display = ['session', 'scenario_control', 'conformity', 'points_earned']
