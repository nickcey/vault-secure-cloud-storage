"""
Courriels de Vault : mise en page HTML aux couleurs de l'application, avec une
version texte équivalente pour les messageries qui n'affichent pas le HTML.

Mise en page en tableaux et styles en ligne : c'est ce que les messageries
(Gmail, Outlook, applications mobiles) affichent de façon fiable.
"""
import re
from html import escape

# Couleurs de l'interface de Vault
BG = '#0b0606'          # fond de page
CARD = '#150b0c'        # carte
EDGE = '#3a1519'        # bordures
BONE = '#f3e6e4'        # texte principal
ASH = '#a8999a'         # texte secondaire
EMBER = '#ff3b44'       # rouge vif (accents)
EMBER_DARK = '#c81e2c'  # rouge foncé (boutons)

FONT = "Arial, 'Helvetica Neue', Helvetica, sans-serif"
MONO = "'Courier New', Consolas, monospace"


def _fold(html, limit=500):
    """Lignes courtes : la norme SMTP refuse les lignes de plus de 998 caractères."""
    html = re.sub(r'>\s*<', '>\n<', html)
    out = []
    for line in html.split('\n'):
        while len(line) > limit:
            cut = line.rfind(' ', 0, limit)
            if cut <= 0:
                break
            out.append(line[:cut])
            line = line[cut + 1:]
        out.append(line)
    return '\n'.join(out)


def _p(text):
    return (f'<p style="margin:0 0 16px;font-family:{FONT};font-size:15px;line-height:1.6;'
            f'color:{BONE};">{text}</p>')


def render(title, paragraphs, *, greeting=None, code=None, code_label=None, code_note=None,
           notice=None, button=None, preheader=None, text_label=None, copy_url=None, lang='fr'):
    """
    Construit un courriel. Renvoie (html, texte).

    title       : titre affiché en haut de la carte
    paragraphs  : liste de paragraphes (texte brut, échappé ici)
    greeting    : « Bonjour Awa, » (facultatif)
    code        : code ou mot de passe à mettre en valeur (facultatif)
    code_label  : libellé au-dessus du code ; code_note : ligne sous le code
    text_label  : phrase de la version texte (« Votre code est : 123456 »)
    copy_url    : adresse de la page « Copier » (bouton sous le code)
    notice      : encadré d'avertissement (texte brut)
    button      : (libellé, url) pour un bouton d'action
    preheader   : aperçu affiché dans la liste des messages
    lang        : 'en' traduit les textes fixes du gabarit (les autres sont traduits par l'appelant)
    """
    from i18n_en import translate
    tr = (lambda x: translate(x, 'en')) if lang == 'en' else (lambda x: x)
    e = escape
    body = []
    if greeting:
        body.append(_p(e(greeting)))
    for para in paragraphs:
        body.append(_p(e(para)))
    if code:
        body.append(
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:6px 0 22px;">'
            f'<tr><td align="center" bgcolor="{BG}" style="background-color:{BG};border:1px solid {EDGE};border-radius:12px;padding:20px 12px;">'
            + (f'<div style="font-family:{FONT};font-size:11px;letter-spacing:2px;text-transform:uppercase;'
               f'color:{ASH};margin-bottom:10px;">{e(code_label)}</div>' if code_label else '')
            # Un seul mot, sélectionnable d'un appui long (et d'un toucher dans les messageries
            # qui respectent user-select) ; l'espacement est visuel et n'entre pas dans la copie.
            + f'<div style="font-family:{MONO};font-size:{30 if len(code) <= 8 else 22}px;font-weight:bold;'
              f'letter-spacing:{6 if len(code) <= 8 else 3}px;color:{EMBER};word-break:break-all;'
              f'-webkit-user-select:all;user-select:all;">{e(code)}</div>'
            + (f'<div style="font-family:{FONT};font-size:12px;color:{ASH};margin-top:10px;">{e(code_note)}</div>'
               if code_note else '')
            + (f'<table role="presentation" cellpadding="0" cellspacing="0" align="center" style="margin:14px auto 0;"><tr>'
               f'<td bgcolor="{CARD}" style="border:1px solid {EMBER_DARK};border-radius:8px;background-color:{CARD};">'
               f'<a href="{e(copy_url)}" style="display:inline-block;padding:9px 18px;font-family:{FONT};font-size:13px;'
               f'font-weight:bold;color:{EMBER};text-decoration:none;">'
               + e(tr("📋 Copier " + ("le code" if code.isdigit() else "le mot de passe")))
               + '</a></td></tr></table>' if copy_url else '')
            + f'<div style="font-family:{FONT};font-size:11px;color:{ASH};margin-top:8px;">'
            + e(tr(("Ou appuyez" if copy_url else "Appuyez") + " longuement sur "
                   + ("le code" if code.isdigit() else "le mot de passe") + " pour le sélectionner."))
            + '</div>'
            + '</td></tr></table>')
    if button:
        label, url = button
        body.append(
            f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:4px 0 22px;"><tr>'
            f'<td bgcolor="{EMBER_DARK}" style="border-radius:10px;background-color:{EMBER_DARK};">'
            f'<a href="{e(url)}" style="display:inline-block;padding:13px 26px;font-family:{FONT};font-size:14px;'
            f'font-weight:bold;letter-spacing:1px;text-transform:uppercase;color:#ffffff;text-decoration:none;'
            f'border-radius:10px;">{e(label)}</a></td></tr></table>')
    if notice:
        body.append(
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 18px;">'
            f'<tr><td bgcolor="#21100f" style="border-left:3px solid {EMBER};background-color:#21100f;'
            f'padding:12px 14px;border-radius:6px;font-family:{FONT};font-size:13px;line-height:1.55;color:{BONE};">'
            f'{e(notice)}</td></tr></table>')

    pre = e(preheader or title)
    html = f"""<!DOCTYPE html>
<html lang="{'en' if lang == 'en' else 'fr'}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark"><meta name="supported-color-schemes" content="dark">
<style>:root{{color-scheme:dark;supported-color-schemes:dark;}} body{{margin:0;padding:0;background-color:{BG};}}</style>
<title>{e(title)}</title></head>
<body bgcolor="{BG}" style="margin:0;padding:0;background-color:{BG};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{pre}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="{BG}" style="background-color:{BG};">
<tr><td align="center" bgcolor="{BG}" style="background-color:{BG};padding:28px 12px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;">
    <tr><td style="padding:0 4px 18px;">
      <table role="presentation" cellpadding="0" cellspacing="0"><tr>
        <td bgcolor="{EMBER_DARK}" style="width:38px;height:38px;background-color:{EMBER_DARK};border-radius:10px;text-align:center;
                   font-family:{FONT};font-size:20px;font-weight:bold;color:#ffffff;line-height:38px;">V</td>
        <td style="padding-left:12px;font-family:{FONT};font-size:18px;letter-spacing:5px;color:{BONE};">VAULT</td>
      </tr></table>
    </td></tr>
    <tr><td bgcolor="{CARD}" style="background-color:{CARD};border:1px solid {EDGE};border-radius:16px;overflow:hidden;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
        <td bgcolor="{EMBER_DARK}" height="4" style="height:4px;line-height:4px;font-size:0;background-color:{EMBER_DARK};">&nbsp;</td>
      </tr></table>
      <div style="padding:30px 30px 14px;">
        <h1 style="margin:0 0 20px;font-family:{FONT};font-size:21px;line-height:1.3;color:{BONE};">{e(title)}</h1>
        {''.join(body)}
      </div>
    </td></tr>
    <tr><td style="padding:18px 8px 0;font-family:{FONT};font-size:11.5px;line-height:1.6;color:{ASH};text-align:center;">
      {e(tr('Vault · stockage en ligne chiffré de bout en bout'))}<br>
      {e(tr('Vault ne vous demandera jamais votre mot de passe ni votre phrase de récupération.'))}<br>
      {e(tr('Ce message a été envoyé automatiquement, merci de ne pas y répondre.'))}
    </td></tr>
  </table>
</td></tr></table>
</body></html>"""

    html = _fold(html)

    # Version texte
    lines = [title, '=' * len(title), '']
    if greeting:
        lines += [greeting, '']
    for para in paragraphs:
        lines += [para, '']
    if code:
        lines += [f'{text_label or code_label or "Code"}{":" if lang == "en" else " :"} {code}', '']
        if code_note:
            lines += [code_note, '']
    if button:
        lines += [f'{button[0]} : {button[1]}', '']
    if notice:
        lines += [notice, '']
    lines += ['--', tr('Vault · stockage en ligne chiffré de bout en bout'),
              tr('Vault ne vous demandera jamais votre mot de passe ni votre phrase de récupération.')]
    return html, '\n'.join(lines)
