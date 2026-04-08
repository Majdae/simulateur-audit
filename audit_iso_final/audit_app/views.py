from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib import messages
from django.db import models as db_models
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db import transaction
import io

from .models import (
    Scenario, ISOControl, ScenarioControl, Evidence,
    AuditSession, ControlEvaluation
)

# -----------------------------------------------------------------
# SCORING RULES (base sur le statut choisi uniquement)
# conforme           = 5 points
# partiel            = 2 points
# non_conforme       = 0 points
# na                 = 1 point
# Max = 5 pts x 20 controles = 100 points
# -----------------------------------------------------------------
POINTS_MAP = {'conforme': 5, 'partiel': 2, 'non_conforme': 0, 'na': 1}

SCENARIO_ICONS = [
    'H', 'EC', 'BQ', 'ENT', 'IND', 'EDU', 'ADM', 'SAN', 'LOG', 'MED',
]


def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'audit_app/home.html')


def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Compte cree avec succes. Bienvenue dans Learn=>Audit.')
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'audit_app/register.html', {'form': form})


@login_required
def dashboard(request):
    
    sessions = AuditSession.objects.filter(user=request.user).select_related('scenario')
    active_sessions = sessions.filter(status='en_cours')
    completed_sessions = sessions.filter(status='termine')
    completed_count = completed_sessions.count()   # compter AVANT le slice
    active_count = active_sessions.count()
    total_audits = sessions.count()
    avg_score = 0
    if completed_sessions.exists():
        scores = [s.score_percent for s in completed_sessions]
        avg_score = int(sum(scores) / len(scores))
    
    ctx = {
        'active_sessions': active_sessions,
        'active_count': active_count, 
        'completed_sessions': completed_sessions[:5],
        'completed_count': completed_count, 
        'total_audits': total_audits,
        'avg_score': avg_score,
        'scenarios_count': Scenario.objects.filter(is_active=True).count(),
    }
    return render(request, 'audit_app/dashboard.html', ctx)


@login_required
def scenario_list(request):
    sector_filter = request.GET.get('sector', '')
    difficulty_filter = request.GET.get('difficulty', '')

    scenarios = Scenario.objects.filter(is_active=True)
    if sector_filter:
        scenarios = scenarios.filter(sector=sector_filter)
    if difficulty_filter:
        scenarios = scenarios.filter(difficulty=difficulty_filter)

    raw_sessions = AuditSession.objects.filter(user=request.user)
    user_sessions = {s.scenario_id: s for s in raw_sessions}

    ctx = {
        'scenarios': scenarios,
        'user_sessions': user_sessions,
        'sector_choices': Scenario.SECTOR_CHOICES,
        'difficulty_choices': Scenario.DIFFICULTY_CHOICES,
        'sector_filter': sector_filter,
        'difficulty_filter': difficulty_filter,
    }
    return render(request, 'audit_app/scenario_list.html', ctx)


@login_required
def start_audit(request, scenario_id):
    scenario = get_object_or_404(Scenario, pk=scenario_id, is_active=True)

    existing = AuditSession.objects.filter(
        user=request.user, scenario=scenario, status='en_cours'
    ).first()
    if existing:
        return redirect('audit_overview', session_id=existing.id)

    total_controls = scenario.scenario_controls.count()
    session = AuditSession.objects.create(
        user=request.user,
        scenario=scenario,
        max_score=total_controls * 5,   # 5 pts per control, 20 controls = 100
    )
    messages.success(request, f'Audit de {scenario.company_name} demarre.')
    return redirect('audit_overview', session_id=session.id)


@login_required
def audit_overview(request, session_id):
    session = get_object_or_404(AuditSession, pk=session_id, user=request.user)
    scenario = session.scenario

    sc_list = scenario.scenario_controls.select_related('control').all()
    evaluated_ids = set(
        session.control_evaluations.values_list('scenario_control_id', flat=True)
    )

    controls_data = []
    for sc in sc_list:
        ev = session.control_evaluations.filter(scenario_control=sc).first()
        controls_data.append({'sc': sc, 'evaluated': sc.id in evaluated_ids, 'evaluation': ev})

    ctx = {
        'session': session,
        'scenario': scenario,
        'controls_data': controls_data,
        'evaluated_count': len(evaluated_ids),
        'total_count': sc_list.count(),
    }
    return render(request, 'audit_app/audit_overview.html', ctx)


@login_required
def audit_control(request, session_id, sc_id):
    session = get_object_or_404(AuditSession, pk=session_id, user=request.user)
    sc = get_object_or_404(ScenarioControl, pk=sc_id, scenario=session.scenario)
    control = sc.control
    evidences = sc.evidences.all()
    evaluation = ControlEvaluation.objects.filter(session=session, scenario_control=sc).first()

    all_scs = list(session.scenario.scenario_controls.order_by('order').values_list('id', flat=True))
    current_idx = all_scs.index(sc.id)
    prev_sc_id = all_scs[current_idx - 1] if current_idx > 0 else None
    next_sc_id = all_scs[current_idx + 1] if current_idx < len(all_scs) - 1 else None

    ctx = {
        'session': session,
        'sc': sc,
        'control': control,
        'evidences': evidences,
        'evaluation': evaluation,
        'conformity_choices': ControlEvaluation.CONFORMITY_CHOICES,
        'risk_choices': ControlEvaluation.RISK_LEVEL_CHOICES,
        'points_map': POINTS_MAP,
        'prev_sc_id': prev_sc_id,
        'next_sc_id': next_sc_id,
        'current_idx': current_idx + 1,
        'total': len(all_scs),
    }
    return render(request, 'audit_app/audit_control.html', ctx)


@login_required
def get_evidence(request, session_id, sc_id, ev_id):
    session = get_object_or_404(AuditSession, pk=session_id, user=request.user)
    sc = get_object_or_404(ScenarioControl, pk=sc_id)
    evidence = get_object_or_404(Evidence, pk=ev_id, scenario_control=sc)
    return JsonResponse({
        'id': evidence.id,
        'title': evidence.title,
        'type': evidence.get_evidence_type_display(),
        'content': evidence.content,
    })


@login_required
def evaluate_control(request, session_id, sc_id):
    if request.method != 'POST':
        return redirect('audit_control', session_id=session_id, sc_id=sc_id)

    session = get_object_or_404(AuditSession, pk=session_id, user=request.user)
    sc = get_object_or_404(ScenarioControl, pk=sc_id, scenario=session.scenario)

    conformity      = request.POST.get('conformity', '')
    justification   = request.POST.get('justification', '').strip()
    risk_level      = request.POST.get('risk_level', '')
    risk_probability = int(request.POST.get('risk_probability', 1))
    risk_severity    = int(request.POST.get('risk_severity', 1))
    recommendation   = request.POST.get('recommendation', '').strip()
    evidence_ids     = request.POST.getlist('evidences_consulted')

    if conformity not in POINTS_MAP:
        messages.error(request, 'Veuillez selectionner un statut de conformite.')
        return redirect('audit_control', session_id=session_id, sc_id=sc_id)

    # Score base uniquement sur le statut choisi
    points = POINTS_MAP.get(conformity, 0)

    with transaction.atomic():
        ev_obj, _ = ControlEvaluation.objects.update_or_create(
            session=session,
            scenario_control=sc,
            defaults={
                'conformity': conformity,
                'justification': justification,
                'risk_level': risk_level,
                'risk_probability': risk_probability,
                'risk_severity': risk_severity,
                'recommendation': recommendation,
                'points_earned': points,
                'is_correct': True,
            }
        )
        if evidence_ids:
            ev_obj.evidences_consulted.set(Evidence.objects.filter(id__in=evidence_ids))

        # Recalculate total session score
        session.score = sum(ce.points_earned for ce in session.control_evaluations.all())
        session.save()

    label = {'conforme': 'Conforme', 'partiel': 'Partiellement conforme',
             'non_conforme': 'Non conforme', 'na': 'Non applicable'}.get(conformity, conformity)
    messages.success(request, f'Evaluation enregistree : {label} — {points}/5 points.')

    all_scs = list(session.scenario.scenario_controls.order_by('order').values_list('id', flat=True))
    current_idx = all_scs.index(sc.id)
    if current_idx < len(all_scs) - 1:
        return redirect('audit_control', session_id=session_id, sc_id=all_scs[current_idx + 1])
    return redirect('audit_overview', session_id=session_id)


@login_required
def complete_audit(request, session_id):
    session = get_object_or_404(AuditSession, pk=session_id, user=request.user)
    if request.method == 'POST':
        session.status = 'termine'
        session.completed_at = timezone.now()
        session.save()
        messages.success(request, 'Audit termine. Consultez votre rapport.')
        return redirect('audit_report', session_id=session_id)
    return redirect('audit_overview', session_id=session_id)


@login_required
def audit_report(request, session_id):
    session = get_object_or_404(AuditSession, pk=session_id, user=request.user)
    evaluations = session.control_evaluations.select_related(
        'scenario_control__control'
    ).prefetch_related('evidences_consulted').all()

    conformes     = evaluations.filter(conformity='conforme').count()
    non_conformes = evaluations.filter(conformity='non_conforme').count()
    partiels      = evaluations.filter(conformity='partiel').count()
    na            = evaluations.filter(conformity='na').count()
    corrects      = evaluations.filter(is_correct=True).count()

    risk_data = []
    for ev in evaluations.filter(conformity__in=['non_conforme', 'partiel']):
        if ev.risk_level:
            risk_data.append({
                'control': ev.scenario_control.control.code,
                'title': ev.scenario_control.control.title,
                'prob': ev.risk_probability,
                'severity': ev.risk_severity,
                'level': ev.get_risk_level_display(),
                'recommendation': ev.recommendation,
            })

    ctx = {
        'session': session,
        'evaluations': evaluations,
        'conformes': conformes,
        'non_conformes': non_conformes,
        'partiels': partiels,
        'na': na,
        'corrects': corrects,
        'total': evaluations.count(),
        'risk_data': risk_data,
        'points_map': POINTS_MAP,
    }
    return render(request, 'audit_app/audit_report.html', ctx)



@login_required
def audit_report_pdf(request, session_id):
    """Generate and download the audit report as a PDF file."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, HRFlowable, KeepTogether
    )
    from reportlab.platypus.flowables import Flowable

    session = get_object_or_404(AuditSession, pk=session_id, user=request.user)
    evaluations = list(session.control_evaluations.select_related(
        'scenario_control__control'
    ).all())

    # ── Colors ──────────────────────────────────────────────────────
    DARK    = colors.HexColor('#0a0d14')
    BLUE    = colors.HexColor('#2563eb')
    GREEN   = colors.HexColor('#10b981')
    RED     = colors.HexColor('#ef4444')
    ORANGE  = colors.HexColor('#f59e0b')
    LGRAY   = colors.HexColor('#f1f5f9')
    MGRAY   = colors.HexColor('#e2e8f0')
    BORDER  = colors.HexColor('#cbd5e1')
    TEXT    = colors.HexColor('#0f172a')
    TEXT_M  = colors.HexColor('#475569')
    TEXT_L  = colors.HexColor('#94a3b8')
    WHITE   = colors.white

    W, H = A4
    MARGIN = 2 * cm

    def S(name, **kw):
        base = {'fontName': 'Helvetica', 'fontSize': 10, 'textColor': TEXT,
                'leading': 15, 'spaceAfter': 4}
        base.update(kw)
        return ParagraphStyle(name, **base)

    def sp(h=6): return Spacer(1, h)
    def hr(c=BORDER): return HRFlowable(width='100%', thickness=0.5, color=c, spaceBefore=3, spaceAfter=3)

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(DARK)
        canvas.rect(0, 0, W, 20, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont('Helvetica', 8)
        canvas.drawString(MARGIN, 6, f"Rapport d\'audit — {session.scenario.company_name} — {session.user.username}")
        canvas.drawRightString(W - MARGIN, 6, f"Page {doc.page}")
        canvas.restoreState()

    # ── Stats ────────────────────────────────────────────────────────
    conformes     = sum(1 for e in evaluations if e.conformity == 'conforme')
    non_conformes = sum(1 for e in evaluations if e.conformity == 'non_conforme')
    partiels      = sum(1 for e in evaluations if e.conformity == 'partiel')
    na            = sum(1 for e in evaluations if e.conformity == 'na')
    total         = len(evaluations)
    score_pct     = session.score_percent

    # ── Build PDF ────────────────────────────────────────────────────
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=1.5*cm, bottomMargin=2*cm,
        title=f"Rapport d\'audit — {session.scenario.company_name}")

    story = []
    hd = S('hd', fontName='Helvetica-Bold', fontSize=14, textColor=DARK)
    h2 = S('h2', fontName='Helvetica-Bold', fontSize=11, textColor=BLUE)
    bd = S('bd', fontSize=10, textColor=TEXT, leading=14, alignment=TA_JUSTIFY)
    sm = S('sm', fontSize=9, textColor=TEXT_M, leading=13)
    mono = S('mo', fontName='Courier', fontSize=9, textColor=colors.HexColor('#1e40af'),
             backColor=colors.HexColor('#eff6ff'), leading=13)

    def colored_box(text, bg, fg=WHITE):
        t = Table([[Paragraph(text, S('cb', fontName='Helvetica-Bold', fontSize=11,
                                      textColor=fg, leading=14))]],
                  colWidths=[W - 2*MARGIN])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), bg),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('LEFTPADDING', (0,0), (-1,-1), 12),
            ('ROUNDEDCORNERS', [4,4,4,4]),
        ]))
        return t

    def make_table(data, widths, hbg=BLUE):
        t = Table(data, colWidths=widths)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), hbg),
            ('TEXTCOLOR', (0,0), (-1,0), WHITE),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [WHITE, LGRAY]),
            ('GRID', (0,0), (-1,-1), 0.3, BORDER),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        return t

    # ── Cover header ─────────────────────────────────────────────────
    story.append(colored_box(f"RAPPORT D\'AUDIT — {session.scenario.company_name.upper()}", DARK))
    story.append(sp(10))

    meta = [
        ['Entite auditee', session.scenario.company_name],
        ['Secteur', session.scenario.get_sector_display()],
        ['Difficulte', session.scenario.get_difficulty_display()],
        ['Auditeur', session.user.username],
        ['Date debut', session.started_at.strftime('%d/%m/%Y %H:%M')],
        ['Date fin', session.completed_at.strftime('%d/%m/%Y %H:%M') if session.completed_at else 'En cours'],
        ['Statut', 'Termine' if session.status == 'termine' else 'En cours'],
        ['Referentiel', 'ISO 27001 / ISO 27002 / ISO 27005'],
    ]
    t = Table(meta, colWidths=[5*cm, 11*cm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('TEXTCOLOR', (0,0), (0,-1), BLUE),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [WHITE, LGRAY]),
        ('GRID', (0,0), (-1,-1), 0.3, BORDER),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t)
    story.append(sp(14))

    # ── Score verdict ─────────────────────────────────────────────────
    if score_pct >= 70:
        verdict_text = f"BONNE CONFORMITE — {session.score}/{session.max_score} pts ({score_pct}%)"
        verdict_bg = GREEN
    elif score_pct >= 40:
        verdict_text = f"CONFORMITE PARTIELLE — {session.score}/{session.max_score} pts ({score_pct}%)"
        verdict_bg = ORANGE
    else:
        verdict_text = f"NON-CONFORMITE CRITIQUE — {session.score}/{session.max_score} pts ({score_pct}%)"
        verdict_bg = RED

    story.append(colored_box(verdict_text, verdict_bg))
    story.append(sp(10))

    # ── Summary stats ─────────────────────────────────────────────────
    story.append(Paragraph("Synthese de l\'audit", h2))
    story.append(hr(BLUE))
    stats_data = [
        ['Conformes', 'Partiels', 'Non Conformes', 'Non Applicables', 'Total evalues'],
        [str(conformes), str(partiels), str(non_conformes), str(na), str(total)],
    ]
    st = Table(stats_data, colWidths=[(W - 2*MARGIN)/5]*5)
    st.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,1), colors.HexColor('#ecfdf5')),
        ('BACKGROUND', (1,0), (1,1), colors.HexColor('#fffbeb')),
        ('BACKGROUND', (2,0), (2,1), colors.HexColor('#fef2f2')),
        ('BACKGROUND', (3,0), (3,1), LGRAY),
        ('BACKGROUND', (4,0), (4,1), colors.HexColor('#eff6ff')),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('FONTSIZE', (0,1), (-1,1), 18),
        ('TEXTCOLOR', (0,0), (0,-1), GREEN),
        ('TEXTCOLOR', (1,0), (1,-1), ORANGE),
        ('TEXTCOLOR', (2,0), (2,-1), RED),
        ('TEXTCOLOR', (3,0), (3,-1), TEXT_L),
        ('TEXTCOLOR', (4,0), (4,-1), BLUE),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.3, BORDER),
    ]))
    story.append(st)
    story.append(sp(14))

    # ── Scoring legend ─────────────────────────────────────────────────
    story.append(Paragraph("Bareme de scoring", h2))
    story.append(hr())
    scoring_data = [
        ['Statut', 'Points', 'Signification'],
        ['Conforme', '5 / 5', 'Le controle est pleinement respecte'],
        ['Partiellement conforme', '2 / 5', 'Le controle est partiellement respecte'],
        ['Non conforme', '0 / 5', 'Le controle n\'est pas respecte'],
        ['Non applicable', '1 / 5', 'Le controle ne s\'applique pas a ce contexte'],
    ]
    story.append(make_table(scoring_data, [5*cm, 2.5*cm, 8.5*cm]))
    story.append(sp(14))
    story.append(PageBreak())

    # ── Detailed evaluations ──────────────────────────────────────────
    story.append(colored_box("DETAIL DES CONSTATATIONS", colors.HexColor('#1e3a5f')))
    story.append(sp(10))

    for ev in evaluations:
        ctrl = ev.scenario_control.control
        conf = ev.conformity

        if conf == 'conforme':
            badge_bg, badge_fg, badge_text, pts_col = colors.HexColor('#ecfdf5'), GREEN, 'Conforme', GREEN
        elif conf == 'non_conforme':
            badge_bg, badge_fg, badge_text, pts_col = colors.HexColor('#fef2f2'), RED, 'Non Conforme', RED
        elif conf == 'partiel':
            badge_bg, badge_fg, badge_text, pts_col = colors.HexColor('#fffbeb'), ORANGE, 'Partiellement Conforme', ORANGE
        else:
            badge_bg, badge_fg, badge_text, pts_col = LGRAY, TEXT_L, 'Non Applicable', TEXT_L

        # Header row: code + title + status + points
        header_data = [[
            Paragraph(f"<b>{ctrl.code}</b>", S('ch', fontName='Courier', fontSize=9, textColor=BLUE)),
            Paragraph(ctrl.title, S('ct', fontName='Helvetica-Bold', fontSize=10, textColor=TEXT)),
            Paragraph(badge_text, S('cs', fontName='Helvetica-Bold', fontSize=9, textColor=badge_fg)),
            Paragraph(f"<b>{ev.points_earned}/5 pts</b>", S('cp', fontName='Helvetica-Bold', fontSize=10, textColor=pts_col)),
        ]]
        ht = Table(header_data, colWidths=[2*cm, 8*cm, 4*cm, 2*cm])
        ht.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), badge_bg),
            ('TOPPADDING', (0,0), (-1,-1), 7),
            ('BOTTOMPADDING', (0,0), (-1,-1), 7),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 0.3, BORDER),
        ]))
        story.append(ht)

        # Details rows
        details = []
        if ev.justification:
            details.append(['Justification', ev.justification])
        if ev.recommendation:
            details.append(['Recommandation', ev.recommendation])
        if ev.risk_level:
            risk_label = {'faible':'Faible','moyen':'Moyen','eleve':'Eleve','critique':'Critique'}.get(ev.risk_level, ev.risk_level)
            details.append(['Risque', f"{risk_label} (Probabilite : {ev.risk_probability}/5 · Gravite : {ev.risk_severity}/5)"])

        if details:
            detail_data = []
            for label, value in details:
                detail_data.append([
                    Paragraph(label, S('dl', fontName='Helvetica-Bold', fontSize=8, textColor=BLUE)),
                    Paragraph(value, S('dv', fontSize=9, textColor=TEXT_M, leading=13)),
                ])
            dt = Table(detail_data, colWidths=[2.8*cm, 13.2*cm])
            dt.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), WHITE),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                ('LEFTPADDING', (0,0), (-1,-1), 8),
                ('GRID', (0,0), (-1,-1), 0.3, BORDER),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ]))
            story.append(dt)

        story.append(sp(6))

    # ── Risk summary ──────────────────────────────────────────────────
    risk_evals = [e for e in evaluations
                  if e.conformity in ('non_conforme', 'partiel') and e.risk_level]
    if risk_evals:
        story.append(PageBreak())
        story.append(colored_box("TABLEAU DES RISQUES", colors.HexColor('#7c2d12')))
        story.append(sp(10))
        risk_data_rows = [['Controle', 'Statut', 'Probabilite', 'Gravite', 'Niveau de risque']]
        for ev in risk_evals:
            risk_label = {'faible':'Faible','moyen':'Moyen','eleve':'Eleve','critique':'Critique'}.get(ev.risk_level, ev.risk_level)
            status_label = 'Non conforme' if ev.conformity == 'non_conforme' else 'Partiel'
            risk_data_rows.append([
                ev.scenario_control.control.code,
                status_label,
                f"{ev.risk_probability}/5",
                f"{ev.risk_severity}/5",
                risk_label,
            ])
        story.append(make_table(risk_data_rows, [2.5*cm, 3*cm, 2.5*cm, 2.5*cm, 5.5*cm], hbg=colors.HexColor('#7c2d12')))
        story.append(sp(14))

    # ── Footer note ───────────────────────────────────────────────────
    story.append(hr())
    story.append(Paragraph(
        f"Rapport genere automatiquement par Learn=>Audit ISO 2700x · Auditeur : {session.user.username} · {session.started_at.strftime('%d/%m/%Y')}",
        S('ft', fontSize=8, textColor=TEXT_L, alignment=TA_CENTER)
    ))

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    buf.seek(0)

    filename = f"rapport_audit_{session.scenario.company_name.replace(' ', '_')}_{session.id}.pdf"
    response = HttpResponse(buf.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def api_session_progress(request, session_id):
    session = get_object_or_404(AuditSession, pk=session_id, user=request.user)
    return JsonResponse({
        'progress': session.progress_percent,
        'score': session.score,
        'max_score': session.max_score,
        'score_percent': session.score_percent,
    })


# ---- Scenario Management ----

@login_required
def scenario_create(request):
    if request.method == 'POST':
        company_name    = request.POST.get('company_name', '').strip()
        company_size    = request.POST.get('company_size', '').strip()
        title           = request.POST.get('title', '').strip()
        sector          = request.POST.get('sector', '')
        difficulty      = request.POST.get('difficulty', 'intermediaire')
        description     = request.POST.get('description', '').strip()
        company_context = request.POST.get('company_context', '').strip()
        audit_objective = request.POST.get('audit_objective', '').strip()
        sector_icon     = request.POST.get('sector_icon', sector[:3].upper())

        errors = []
        if not company_name:  errors.append('Le nom de l\'entreprise est obligatoire.')
        if not title:         errors.append('Le titre du scenario est obligatoire.')
        if not sector:        errors.append('Le secteur est obligatoire.')
        if not description:   errors.append('La description est obligatoire.')
        if not company_context: errors.append('Le contexte est obligatoire.')
        if not audit_objective: errors.append('L\'objectif est obligatoire.')

        if errors:
            ctx = {
                'errors': errors, 'form_data': request.POST,
                'sector_choices': Scenario.SECTOR_CHOICES,
                'difficulty_choices': Scenario.DIFFICULTY_CHOICES,
            }
            return render(request, 'audit_app/scenario_form.html', ctx)

        scenario = Scenario.objects.create(
            title=title, sector=sector, difficulty=difficulty,
            sector_icon=sector_icon, company_name=company_name,
            company_size=company_size, description=description,
            company_context=company_context, audit_objective=audit_objective,
            is_active=True,
        )
        messages.success(request, f'Scenario "{company_name}" cree. Ajoutez maintenant les controles ISO.')
        return redirect('scenario_add_controls', scenario_id=scenario.id)

    ctx = {
        'sector_choices': Scenario.SECTOR_CHOICES,
        'difficulty_choices': Scenario.DIFFICULTY_CHOICES,
    }
    return render(request, 'audit_app/scenario_form.html', ctx)


@login_required
def scenario_edit(request, scenario_id):
    scenario = get_object_or_404(Scenario, pk=scenario_id)
    if request.method == 'POST':
        scenario.title           = request.POST.get('title', scenario.title).strip()
        scenario.sector          = request.POST.get('sector', scenario.sector)
        scenario.difficulty      = request.POST.get('difficulty', scenario.difficulty)
        scenario.company_name    = request.POST.get('company_name', scenario.company_name).strip()
        scenario.company_size    = request.POST.get('company_size', scenario.company_size).strip()
        scenario.description     = request.POST.get('description', scenario.description).strip()
        scenario.company_context = request.POST.get('company_context', scenario.company_context).strip()
        scenario.audit_objective = request.POST.get('audit_objective', scenario.audit_objective).strip()
        scenario.is_active       = request.POST.get('is_active') == 'on'
        scenario.save()
        messages.success(request, 'Scenario mis a jour.')
        return redirect('scenario_add_controls', scenario_id=scenario.id)

    ctx = {
        'scenario': scenario,
        'sector_choices': Scenario.SECTOR_CHOICES,
        'difficulty_choices': Scenario.DIFFICULTY_CHOICES,
        'editing': True,
    }
    return render(request, 'audit_app/scenario_form.html', ctx)


@login_required
def scenario_delete(request, scenario_id):
    scenario = get_object_or_404(Scenario, pk=scenario_id)
    if request.method == 'POST':
        name = scenario.company_name
        scenario.delete()
        messages.success(request, f'Scenario "{name}" supprime.')
        return redirect('scenario_list')
    return render(request, 'audit_app/scenario_confirm_delete.html', {'scenario': scenario})


@login_required
def scenario_add_controls(request, scenario_id):
    scenario = get_object_or_404(Scenario, pk=scenario_id)
    all_controls = ISOControl.objects.all().order_by('code')
    attached = scenario.scenario_controls.select_related('control').order_by('order')
    attached_ids = set(sc.control_id for sc in attached)

    if request.method == 'POST':
        control_ids = request.POST.getlist('control_ids')
        order_start = attached.count()
        added = 0
        for cid in control_ids:
            try:
                ctrl = ISOControl.objects.get(pk=int(cid))
                if ctrl.id not in attached_ids:
                    ScenarioControl.objects.create(
                        scenario=scenario, control=ctrl, order=order_start + added
                    )
                    attached_ids.add(ctrl.id)
                    added += 1
            except (ISOControl.DoesNotExist, ValueError):
                pass
        if added:
            messages.success(request, f'{added} controle(s) ajoute(s).')
        return redirect('scenario_add_controls', scenario_id=scenario.id)

    from collections import defaultdict
    grouped = defaultdict(list)
    for ctrl in all_controls:
        grouped[ctrl.get_category_display()].append(ctrl)

    ctx = {
        'scenario': scenario,
        'grouped_controls': dict(grouped),
        'attached': attached,
        'attached_ids': attached_ids,
    }
    return render(request, 'audit_app/scenario_add_controls.html', ctx)


@login_required
def scenario_control_delete(request, scenario_id, sc_id):
    scenario = get_object_or_404(Scenario, pk=scenario_id)
    sc = get_object_or_404(ScenarioControl, pk=sc_id, scenario=scenario)
    if request.method == 'POST':
        sc.delete()
        for i, s in enumerate(scenario.scenario_controls.order_by('order')):
            s.order = i
            s.save()
        messages.success(request, 'Controle retire du scenario.')
    return redirect('scenario_add_controls', scenario_id=scenario.id)


@login_required
def scenario_add_evidences(request, scenario_id, sc_id):
    scenario = get_object_or_404(Scenario, pk=scenario_id)
    sc = get_object_or_404(ScenarioControl, pk=sc_id, scenario=scenario)
    evidences = sc.evidences.all()

    if request.method == 'POST':
        ev_title   = request.POST.get('title', '').strip()
        ev_type    = request.POST.get('evidence_type', '')
        ev_content = request.POST.get('content', '').strip()
        ev_hint    = request.POST.get('hint', 'conforme')
        errors = []
        if not ev_title:   errors.append('Le titre est obligatoire.')
        if not ev_type:    errors.append('Le type de preuve est obligatoire.')
        if not ev_content: errors.append('Le contenu est obligatoire.')

        if not errors:
            Evidence.objects.create(
                scenario_control=sc, title=ev_title,
                evidence_type=ev_type, content=ev_content, hint=ev_hint,
            )
            messages.success(request, f'Preuve "{ev_title}" ajoutee.')
            return redirect('scenario_add_evidences', scenario_id=scenario.id, sc_id=sc.id)

        ctx = {
            'scenario': scenario, 'sc': sc, 'evidences': evidences,
            'errors': errors, 'form_data': request.POST,
            'evidence_types': Evidence.EVIDENCE_TYPE_CHOICES,
            'hint_choices': Evidence.CONFORMITY_HINT,
        }
        return render(request, 'audit_app/scenario_add_evidences.html', ctx)

    all_scs = list(scenario.scenario_controls.order_by('order'))
    idx = next((i for i, s in enumerate(all_scs) if s.id == sc.id), 0)
    prev_sc = all_scs[idx - 1] if idx > 0 else None
    next_sc = all_scs[idx + 1] if idx < len(all_scs) - 1 else None

    ctx = {
        'scenario': scenario, 'sc': sc, 'evidences': evidences,
        'evidence_types': Evidence.EVIDENCE_TYPE_CHOICES,
        'hint_choices': Evidence.CONFORMITY_HINT,
        'all_scs': all_scs, 'current_idx': idx + 1,
        'prev_sc': prev_sc, 'next_sc': next_sc,
    }
    return render(request, 'audit_app/scenario_add_evidences.html', ctx)


@login_required
def evidence_delete(request, scenario_id, sc_id, ev_id):
    scenario = get_object_or_404(Scenario, pk=scenario_id)
    sc = get_object_or_404(ScenarioControl, pk=sc_id, scenario=scenario)
    ev = get_object_or_404(Evidence, pk=ev_id, scenario_control=sc)
    if request.method == 'POST':
        ev.delete()
        messages.success(request, 'Preuve supprimee.')
    return redirect('scenario_add_evidences', scenario_id=scenario.id, sc_id=sc.id)


@login_required
def api_controls_list(request):
    q        = request.GET.get('q', '').strip()
    norm     = request.GET.get('norm', '')
    category = request.GET.get('category', '')
    controls = ISOControl.objects.all()
    if q:
        controls = controls.filter(
            db_models.Q(code__icontains=q) | db_models.Q(title__icontains=q)
        )
    if norm:
        controls = controls.filter(norm=norm)
    if category:
        controls = controls.filter(category=category)
    data = [
        {'id': c.id, 'code': c.code, 'title': c.title,
         'category': c.get_category_display(), 'norm': c.get_norm_display()}
        for c in controls[:50]
    ]
    return JsonResponse({'controls': data})
