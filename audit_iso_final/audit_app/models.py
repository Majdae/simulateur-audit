from django.db import models
from django.contrib.auth.models import User


class Scenario(models.Model):
    SECTOR_CHOICES = [
        ('hopital', 'Hopital / Sante'),
        ('ecommerce', 'E-Commerce'),
        ('entreprise', 'Entreprise de Services'),
        ('banque', 'Banque / Finance'),
        ('industrie', 'Industrie / Manufacturing'),
    ]
    DIFFICULTY_CHOICES = [
        ('debutant', 'Debutant'),
        ('intermediaire', 'Intermediaire'),
        ('avance', 'Avance'),
    ]

    title = models.CharField(max_length=200)
    sector = models.CharField(max_length=50, choices=SECTOR_CHOICES)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='intermediaire')
    description = models.TextField()
    company_name = models.CharField(max_length=100)
    company_size = models.CharField(max_length=50)
    company_context = models.TextField()
    audit_objective = models.TextField()
    sector_icon = models.CharField(max_length=10, default='E')  # text abbreviation, no emoji
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.company_name} ({self.get_sector_display()})"

    class Meta:
        verbose_name = "Scenario"
        verbose_name_plural = "Scenarios"


class ISOControl(models.Model):
    NORM_CHOICES = [
        ('27001', 'ISO 27001'),
        ('27002', 'ISO 27002'),
        ('27005', 'ISO 27005'),
    ]
    CATEGORY_CHOICES = [
        ('politique', 'Politique de Securite'),
        ('organisation', 'Organisation de la Securite'),
        ('rh', 'Securite des RH'),
        ('actifs', 'Gestion des Actifs'),
        ('acces', "Controle d'Acces"),
        ('cryptographie', 'Cryptographie'),
        ('physique', 'Securite Physique'),
        ('operations', 'Securite Operationnelle'),
        ('communications', 'Securite des Communications'),
        ('incidents', 'Gestion des Incidents'),
        ('continuite', "Continuite d'Activite"),
        ('conformite', 'Conformite'),
    ]

    code = models.CharField(max_length=20, unique=True)
    norm = models.CharField(max_length=10, choices=NORM_CHOICES, default='27002')
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField()
    objective = models.TextField()
    guidance = models.TextField(blank=True)

    def __str__(self):
        return f"{self.code} - {self.title}"

    class Meta:
        verbose_name = "Controle ISO"
        verbose_name_plural = "Controles ISO"
        ordering = ['code']


class ScenarioControl(models.Model):
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE, related_name='scenario_controls')
    control = models.ForeignKey(ISOControl, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']
        unique_together = ('scenario', 'control')


class Evidence(models.Model):
    EVIDENCE_TYPE_CHOICES = [
        ('document', 'Document / Politique'),
        ('config', 'Configuration Systeme'),
        ('log', 'Extrait de Log'),
        ('interview', 'Compte-rendu Entretien'),
        ('observation', 'Observation Terrain'),
    ]
    CONFORMITY_HINT = [
        ('conforme', 'Conforme'),
        ('non_conforme', 'Non Conforme'),
        ('partiel', 'Partiellement Conforme'),
    ]

    scenario_control = models.ForeignKey(ScenarioControl, on_delete=models.CASCADE, related_name='evidences')
    title = models.CharField(max_length=200)
    evidence_type = models.CharField(max_length=20, choices=EVIDENCE_TYPE_CHOICES)
    content = models.TextField()
    hint = models.CharField(max_length=20, choices=CONFORMITY_HINT)

    def __str__(self):
        return f"[{self.get_evidence_type_display()}] {self.title}"

    class Meta:
        verbose_name = "Preuve"
        verbose_name_plural = "Preuves"


class AuditSession(models.Model):
    STATUS_CHOICES = [
        ('en_cours', 'En cours'),
        ('termine', 'Termine'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='audit_sessions')
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='en_cours')
    score = models.IntegerField(default=0)
    max_score = models.IntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Audit de {self.user.username} - {self.scenario.company_name}"

    @property
    def progress_percent(self):
        total = self.scenario.scenario_controls.count()
        if total == 0:
            return 0
        done = self.control_evaluations.count()
        return int((done / total) * 100)

    @property
    def score_percent(self):
        if self.max_score == 0:
            return 0
        return int((self.score / self.max_score) * 100)

    class Meta:
        verbose_name = "Session d'Audit"
        verbose_name_plural = "Sessions d'Audit"
        ordering = ['-started_at']


class ControlEvaluation(models.Model):
    # Points: conforme=5, partiel=2, non_conforme=0, na=1
    # Max per control = 5  => 20 controls => max_score = 100
    CONFORMITY_CHOICES = [
        ('conforme', 'Conforme'),
        ('non_conforme', 'Non Conforme'),
        ('partiel', 'Partiellement Conforme'),
        ('na', 'Non Applicable'),
    ]
    RISK_LEVEL_CHOICES = [
        ('faible', 'Faible'),
        ('moyen', 'Moyen'),
        ('eleve', 'Eleve'),
        ('critique', 'Critique'),
    ]

    POINTS_MAP = {
        'conforme': 5,
        'partiel': 2,
        'non_conforme': 0,
        'na': 1,
    }

    session = models.ForeignKey(AuditSession, on_delete=models.CASCADE, related_name='control_evaluations')
    scenario_control = models.ForeignKey(ScenarioControl, on_delete=models.CASCADE)
    evidences_consulted = models.ManyToManyField(Evidence, blank=True)
    conformity = models.CharField(max_length=20, choices=CONFORMITY_CHOICES)
    justification = models.TextField(blank=True)
    risk_level = models.CharField(max_length=10, choices=RISK_LEVEL_CHOICES, blank=True)
    risk_probability = models.IntegerField(default=1)
    risk_severity = models.IntegerField(default=1)
    recommendation = models.TextField(blank=True)
    points_earned = models.IntegerField(default=0)
    is_correct = models.BooleanField(default=False)  # did auditeur match the hint?
    evaluated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.scenario_control.control.code} - {self.conformity}"

    class Meta:
        verbose_name = "Evaluation de Controle"
        verbose_name_plural = "Evaluations de Controle"
        unique_together = ('session', 'scenario_control')
