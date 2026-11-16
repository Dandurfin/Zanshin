"""Interface translations - Slovak / English / Japanese / Chinese
(Simplified) / Russian / Spanish / German / French /
Portuguese (Brazil) / Czech / Bulgarian.

The language set = the app's interface (SK/EN/JA) + the most popular
languages of players on Steam (Steam Hardware & Software Survey + Valve
GDC'25 data) + Czech and Bulgarian (0.2).

The whole UI is redrawn from scratch after a language switch (the same
principle as when switching the visual theme), so it is enough to change
`_lang["code"]` and call `tr()` again while building the widgets - no
widget remembers a translation permanently.

NOTE ON TRANSLATIONS: the app is written in Slovak; the other languages
are translations made with the help of AI (Claude) and a native speaker
has not checked them yet (the app says so itself -
`settings.language_note` under the language picker). We recommend having
them reviewed by native speakers before a wide release of the app,
especially the content in guide.* (biomechanics/breathing techniques),
where the precision of the wording really matters.

Czech and Bulgarian have their translation in a separate module
`i18n_cs_bg.py` - it is inserted at the end of this file.
"""

LANG_SK = "sk"
LANG_EN = "en"
LANG_JA = "ja"
LANG_ZH = "zh"
LANG_RU = "ru"
LANG_ES = "es"
LANG_DE = "de"
LANG_FR = "fr"
LANG_PT = "pt"
LANG_CS = "cs"
LANG_BG = "bg"
DEFAULT_LANG = LANG_SK
LANGUAGES = (LANG_SK, LANG_EN, LANG_JA, LANG_ZH, LANG_RU, LANG_ES, LANG_DE, LANG_FR, LANG_PT,
             LANG_CS, LANG_BG)

_lang = {"code": DEFAULT_LANG}


def set_lang(code):
    _lang["code"] = code if code in LANGUAGES else DEFAULT_LANG


def _pick(entry, code, msg_key):
    """Entry text in language `code`; if missing, English, then Slovak.

    Every key should have all languages (tests/test_i18n_keys.py guards
    that) - this is a safety net so that an incomplete entry (e.g. a full
    dict with nine languages for Czech and Bulgarian) never brings down a
    window or shows Slovak to a player who chose another language.
    """
    for kod in (code, LANG_EN, DEFAULT_LANG):
        if kod in entry:
            return entry[kod]
    return msg_key


def _format(entry, code, text, kwargs):
    """`text.format(**kwargs)` - the English source if a translation is broken.

    A mistyped {placeholder} in a translation must not bring down the
    window. Placeholders in the source are guarded by check_before_run.py;
    when English fails too, it is a mistake in the call, not in the
    translation - that one is shown.
    """
    if not kwargs:
        return text
    try:
        return text.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        if code == LANG_EN or LANG_EN not in entry:
            raise
        return entry[LANG_EN].format(**kwargs)


def tr(msg_key, **kwargs):
    entry = STRINGS.get(msg_key)
    if entry is None:
        return msg_key
    code = _lang["code"]
    return _format(entry, code, _pick(entry, code, msg_key), kwargs)


# NUMBER IN A SENTENCE (0.3, UX audit, batch 4). "trend -2.0 BPM/týždeň"
# had an English point and a hyphen in a Slovak sentence. Only English,
# Japanese and Chinese write a decimal point; the other eight languages
# of the app write a comma. A negative number gets a real minus sign
# (U+2212), not a hyphen; `sign=True` keeps the plus too (trend "+1,5").
_DESATINNA_BODKA = frozenset({LANG_EN, LANG_JA, LANG_ZH})
ZNAK_MINUS = "−"


def cislo(x, decimals=0, sign=False, lang=None):
    """Number `x` with `decimals` decimal places for a sentence in the app's
    language (or `lang`). What is not a number is returned as text;
    infinity and NaN as "—". Zero is never written with a minus sign
    ("−0,0" would lie)."""
    try:
        hodnota = float(x)
    except (TypeError, ValueError):
        return str(x)
    if hodnota != hodnota or hodnota in (float("inf"), float("-inf")):
        return "—"
    decimals = max(0, int(decimals))
    text = f"{abs(hodnota):.{decimals}f}"
    if (lang or _lang["code"]) not in _DESATINNA_BODKA:
        text = text.replace(".", ",")
    if float(text.replace(",", ".")) == 0.0:
        return text           # zero after rounding: no "+0,0" and no "−0,0"
    if hodnota < 0:
        return ZNAK_MINUS + text
    return ("+" + text) if sign else text


# Special value for "In-game language" - stick to the interface language.
LANG_SAME_AS_APP = "app"


def _win_locale():
    """Locale code of the logged-in user, e.g. 'de-DE'. Empty = unknown.

    Separate from `system_lang()` because of tests - this is the only
    piece that asks the operating system, so it can be swapped in a test
    and the rest of the mapping checked on all languages
    (tests/test_i18n_cs_bg.py).
    """
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(85)
        if ctypes.windll.kernel32.GetUserDefaultLocaleName(buf, 85):
            return buf.value or ""
    except Exception:
        pass
    try:
        import locale
        return locale.getdefaultlocale()[0] or ""
    except Exception:
        return ""


def system_lang(default=LANG_EN):
    """Windows language mapped to one of our eleven.

    WHY THIS EXISTS: on the first start the app used to set itself to
    SLOVAK - because that is what the author wrote it in. But a German, a
    Brazilian or a Japanese person downloads it too, and the first thing
    they see is a language they do not understand, and they have to look
    for it in the settings. That is why on the first start the system
    language is taken, and when we do not have it among our eleven,
    English - not Slovak.

    The player's saved choice always takes precedence; this is only asked
    when there is none yet.
    """
    kod = _win_locale() or ""
    primarny = kod.replace("_", "-").lower().split("-")[0]
    # A Czech Windows got Slovak before 0.2 (Czech was not among the
    # languages); since 0.2 Czech has its own translation, Bulgarian too.
    if primarny in LANGUAGES:
        return primarny
    return default


def tr_lang(code, msg_key, **kwargs):
    """Translation into a SPECIFIC language, regardless of the UI language.

    It is for what the app draws INTO THE GAME (the HUD bottom left, the
    labels under the visuals). Those are not seen only by the player -
    viewers on a stream and buyers on store screenshots see them too. So
    the interface can be in Slovak and the in-game text in English.

    `code` outside `LANGUAGES` (typically `LANG_SAME_AS_APP`) means "use
    the interface language".
    """
    entry = STRINGS.get(msg_key)
    if entry is None:
        return msg_key
    code = code if code in LANGUAGES else _lang["code"]
    return _format(entry, code, _pick(entry, code, msg_key), kwargs)


STRINGS = {
    'nav.zvuk': {
        'sk': 'Zvuk / Audio',
        'en': 'Sound / Audio',
        'ja': 'サウンド / オーディオ',
        'zh': '声音 / 音频',
        'ru': 'Звук / Аудио',
        'es': 'Sonido / Audio',
        'de': 'Sound / Audio',
        'fr': 'Son / Audio',
        'pt': 'Som / Áudio',
    },
    'nav.nastavenia': {
        'sk': 'Nastavenia',
        'en': 'Settings',
        'ja': '設定',
        'zh': '设置',
        'ru': 'Настройки',
        'es': 'Ajustes',
        'de': 'Einstellungen',
        'fr': 'Paramètres',
        'pt': 'Configurações',
    },
    'onboarding.welcome': {
        'sk': 'Vitaj v appke {app}',
        'en': 'Welcome to {app}',
        'ja': '{app} へようこそ',
        'zh': '欢迎使用 {app}',
        'ru': 'Добро пожаловать в {app}',
        'es': 'Te damos la bienvenida a {app}',
        'de': 'Willkommen bei {app}',
        'fr': 'Bienvenue dans {app}',
        'pt': 'Boas-vindas ao {app}',
    },
    'onboarding.confirm': {
        'sk': 'Vstúpiť do hry (Aktivovať Zanshin)',
        'en': 'Enter the game (Activate Zanshin)',
        'ja': 'ゲームに入る（Zanshin 起動）',
        'zh': '进入游戏（启动 Zanshin）',
        'ru': 'Войти в игру (активировать Zanshin)',
        'es': 'Entrar al juego (activar Zanshin)',
        'de': 'Ins Spiel eintreten (Zanshin aktivieren)',
        'fr': 'Entrer dans le jeu (activer Zanshin)',
        'pt': 'Entrar no jogo (ativar Zanshin)',
    },
    'assets.preparing': {
        'sk': 'Pripravujem zvuky…',
        'en': 'Preparing sounds…',
        'ja': 'サウンドを準備中…',
        'zh': '正在准备声音…',
        'ru': 'Готовлю звуки…',
        'es': 'Preparando sonidos…',
        'de': 'Klänge werden vorbereitet…',
        'fr': 'Préparation des sons…',
        'pt': 'Preparando os sons…',
    },
    'theme.zen.label': {
        'sk': 'Sumi',
        'en': 'Sumi',
        'ja': 'Sumi',
        'zh': 'Sumi',
        'ru': 'Sumi',
        'es': 'Sumi',
        'de': 'Sumi',
        'fr': 'Sumi',
        'pt': 'Sumi',
    },
    'theme.modern.label': {
        'sk': 'Aizome',
        'en': 'Aizome',
        'ja': 'Aizome',
        'zh': 'Aizome',
        'ru': 'Aizome',
        'es': 'Aizome',
        'de': 'Aizome',
        'fr': 'Aizome',
        'pt': 'Aizome',
    },
    'banner.edge_missing': {
        'sk': "Knižnica edge-tts nie je nainštalovaná, preto počuješ starý robotický hlas. Nainštaluj ju príkazom:  pip install edge-tts  a potom klikni na 'Skúsiť znova'.",
        'en': "The edge-tts library isn't installed, so you're hearing the old robotic voice. Install it with:  pip install edge-tts  then click 'Try again'.",
        'ja': 'edge-tts ライブラリがインストールされていないため、古いロボット音声になっています。次のコマンドでインストールしてください：  pip install edge-tts  その後「もう一度試す」をクリックしてください。',
        'zh': '未安装 edge-tts 库，因此你听到的是旧版机械音。安装方法：  pip install edge-tts  然后点击"重试"。',
        'ru': 'Библиотека edge-tts не установлена, поэтому ты слышишь старый роботизированный голос. Установи её командой:  pip install edge-tts  затем нажми «Повторить».',
        'es': 'La librería edge-tts no está instalada, por eso escuchas la voz robótica antigua. Instálala con:  pip install edge-tts  y luego pulsa «Reintentar».',
        'de': 'Die edge-tts-Bibliothek ist nicht installiert, deshalb hörst du die alte Roboterstimme. Installiere sie mit:  pip install edge-tts  und klicke dann auf „Erneut versuchen“.',
        'fr': "La bibliothèque edge-tts n'est pas installée, c'est pourquoi tu entends l'ancienne voix robotique. Installe-la avec :  pip install edge-tts  puis clique sur « Réessayer ».",
        'pt': 'A biblioteca edge-tts não está instalada, por isso você está ouvindo a voz robótica antiga. Instale com:  pip install edge-tts  e depois clique em "Tentar novamente".',
    },
    'common.retry': {
        'sk': 'Skúsiť znova',
        'en': 'Try again',
        'ja': 'もう一度試す',
        'zh': '重试',
        'ru': 'Повторить',
        'es': 'Reintentar',
        'de': 'Erneut versuchen',
        'fr': 'Réessayer',
        'pt': 'Tentar novamente',
    },
    'profile.default_name': {
        'sk': 'Predvolený',
        'en': 'Default',
        'ja': 'デフォルト',
        'zh': '默认',
        'ru': 'По умолчанию',
        'es': 'Predeterminado',
        'de': 'Standard',
        'fr': 'Par défaut',
        'pt': 'Padrão',
    },
    'profile.new': {
        'sk': '+ Nový',
        'en': '+ New',
        'ja': '+ 新規',
        'zh': '+ 新建',
        'ru': '+ Новый',
        'es': '+ Nuevo',
        'de': '+ Neu',
        'fr': '+ Nouveau',
        'pt': '+ Novo',
    },
    'profile.delete': {
        'sk': '🗑',
        'en': '🗑',
        'ja': '🗑',
        'zh': '🗑',
        'ru': '🗑',
        'es': '🗑',
        'de': '🗑',
        'fr': '🗑',
        'pt': '🗑',
    },
    'profile.new_title': {
        'sk': 'Nový profil',
        'en': 'New profile',
        'ja': '新規プロファイル',
        'zh': '新建配置文件',
        'ru': 'Новый профиль',
        'es': 'Nuevo perfil',
        'de': 'Neues Profil',
        'fr': 'Nouveau profil',
        'pt': 'Novo perfil',
    },
    'profile.name_label': {
        'sk': 'Názov profilu (napr. názov hry):',
        'en': 'Profile name (e.g. game title):',
        'ja': 'プロファイル名（例: ゲーム名）:',
        'zh': '配置文件名称（例如游戏名）：',
        'ru': 'Название профиля (например, название игры):',
        'es': 'Nombre del perfil (ej. título del juego):',
        'de': 'Profilname (z. B. Spieltitel):',
        'fr': 'Nom du profil (ex. titre du jeu) :',
        'pt': 'Nome do perfil (ex.: título do jogo):',
    },
    'profile.duplicate_name': {
        'sk': 'Profil s týmto názvom už existuje.',
        'en': 'A profile with this name already exists.',
        'ja': 'その名前のプロファイルは既に存在します。',
        'zh': '已存在同名的配置文件。',
        'ru': 'Профиль с таким названием уже существует.',
        'es': 'Ya existe un perfil con este nombre.',
        'de': 'Ein Profil mit diesem Namen existiert bereits.',
        'fr': 'Un profil portant ce nom existe déjà.',
        'pt': 'Já existe um perfil com esse nome.',
    },
    'profile.cannot_delete_last': {
        'sk': 'Musí zostať aspoň jeden profil.',
        'en': 'At least one profile must remain.',
        'ja': '少なくとも1つのプロファイルが必要です。',
        'zh': '至少需要保留一个配置文件。',
        'ru': 'Должен остаться хотя бы один профиль.',
        'es': 'Debe quedar al menos un perfil.',
        'de': 'Mindestens ein Profil muss übrig bleiben.',
        'fr': 'Il doit rester au moins un profil.',
        'pt': 'Deve restar pelo menos um perfil.',
    },
    'profile.confirm_delete': {
        'sk': 'Naozaj odstrániť profil „{name}“ aj so všetkými jeho pripomienkami?',
        'en': 'Really delete the profile “{name}” and all of its cues?',
        'ja': 'プロファイル「{name}」とそのすべての合図を削除しますか？',
        'zh': '确定要删除配置文件「{name}」及其所有提示吗？',
        'ru': 'Действительно удалить профиль «{name}» и все его подсказки?',
        'es': '¿Eliminar de verdad el perfil «{name}» y todos sus avisos?',
        'de': 'Profil „{name}“ und alle seine Hinweise wirklich löschen?',
        'fr': 'Vraiment supprimer le profil « {name} » et tous ses rappels ?',
        'pt': 'Excluir mesmo o perfil “{name}” e todos os seus avisos?',
    },
    'log.profile_switched': {
        'sk': "Prepnuté na profil '{name}'.",
        'en': "Switched to profile '{name}'.",
        'ja': 'プロファイル「{name}」に切り替えました。',
        'zh': '已切换到配置文件「{name}」。',
        'ru': 'Переключено на профиль «{name}».',
        'es': 'Cambiado al perfil «{name}».',
        'de': 'Zu Profil „{name}“ gewechselt.',
        'fr': 'Basculé sur le profil « {name} ».',
        'pt': 'Alternado para o perfil "{name}".',
    },
    'log.profile_created': {
        'sk': "Vytvorený profil '{name}'.",
        'en': "Profile '{name}' created.",
        'ja': 'プロファイル「{name}」を作成しました。',
        'zh': '已创建配置文件「{name}」。',
        'ru': 'Профиль «{name}» создан.',
        'es': 'Perfil «{name}» creado.',
        'de': 'Profil „{name}“ erstellt.',
        'fr': 'Profil « {name} » créé.',
        'pt': 'Perfil "{name}" criado.',
    },
    'log.profile_deleted': {
        'sk': 'Profil odstránený.',
        'en': 'Profile deleted.',
        'ja': 'プロファイルを削除しました。',
        'zh': '配置文件已删除。',
        'ru': 'Профиль удалён.',
        'es': 'Perfil eliminado.',
        'de': 'Profil gelöscht.',
        'fr': 'Profil supprimé.',
        'pt': 'Perfil excluído.',
    },
    'profile.export': {
        'sk': '📋 Kopírovať kód profilu',
        'en': '📋 Copy profile code',
        'ja': '📋 プロファイルコードをコピー',
        'zh': '📋 复制配置代码',
        'ru': '📋 Скопировать код профиля',
        'es': '📋 Copiar código del perfil',
        'de': '📋 Profilcode kopieren',
        'fr': '📋 Copier le code du profil',
        'pt': '📋 Copiar código do perfil',
    },
    'profile.import': {
        'sk': '📥 Importovať profil',
        'en': '📥 Import profile',
        'ja': '📥 プロファイルをインポート',
        'zh': '📥 导入配置文件',
        'ru': '📥 Импортировать профиль',
        'es': '📥 Importar perfil',
        'de': '📥 Profil importieren',
        'fr': '📥 Importer un profil',
        'pt': '📥 Importar perfil',
    },
    'log.profile_exported': {
        'sk': "Kód profilu '{name}' skopírovaný do schránky ({n} znakov).",
        'en': "Profile code for '{name}' copied to clipboard ({n} characters).",
        'ja': 'プロファイル「{name}」のコードをクリップボードにコピーしました（{n}文字）。',
        'zh': '「{name}」的配置代码已复制到剪贴板（{n} 个字符）。',
        'ru': 'Код профиля «{name}» скопирован в буфер обмена ({n} символов).',
        'es': 'Código del perfil «{name}» copiado al portapapeles ({n} caracteres).',
        'de': 'Profilcode für „{name}“ in die Zwischenablage kopiert ({n} Zeichen).',
        'fr': 'Code du profil « {name} » copié dans le presse-papiers ({n} caractères).',
        'pt': 'Código do perfil "{name}" copiado para a área de transferência ({n} caracteres).',
    },
    'log.profile_export_error': {
        'sk': 'Export profilu zlyhal: {err}',
        'en': 'Profile export failed: {err}',
        'ja': 'プロファイルのエクスポートに失敗しました: {err}',
        'zh': '配置文件导出失败：{err}',
        'ru': 'Не удалось экспортировать профиль: {err}',
        'es': 'Fallo al exportar el perfil: {err}',
        'de': 'Profilexport fehlgeschlagen: {err}',
        'fr': "Échec de l'export du profil : {err}",
        'pt': 'Falha ao exportar o perfil: {err}',
    },
    'log.profile_imported': {
        'sk': "Profil '{name}' importovaný a aktivovaný.",
        'en': "Profile '{name}' imported and activated.",
        'ja': 'プロファイル「{name}」をインポートして有効化しました。',
        'zh': '配置文件「{name}」已导入并激活。',
        'ru': 'Профиль «{name}» импортирован и активирован.',
        'es': 'Perfil «{name}» importado y activado.',
        'de': 'Profil „{name}“ importiert und aktiviert.',
        'fr': 'Profil « {name} » importé et activé.',
        'pt': 'Perfil "{name}" importado e ativado.',
    },
    'import.title': {
        'sk': 'Importovať profil',
        'en': 'Import profile',
        'ja': 'プロファイルをインポート',
        'zh': '导入配置文件',
        'ru': 'Импорт профиля',
        'es': 'Importar perfil',
        'de': 'Profil importieren',
        'fr': 'Importer un profil',
        'pt': 'Importar perfil',
    },
    'import.hint': {
        'sk': 'Vlož sem kód profilu, ktorý ti niekto poslal (napr. na Discorde):',
        'en': 'Paste the profile code someone sent you (e.g. on Discord):',
        'ja': '誰かから送られたプロファイルコードを貼り付けてください（例: Discord）:',
        'zh': '粘贴别人发给你的配置代码（例如通过 Discord）：',
        'ru': 'Вставь код профиля, который тебе прислали (например, в Discord):',
        'es': 'Pega el código de perfil que alguien te envió (ej. por Discord):',
        'de': 'Füge den Profilcode ein, den dir jemand geschickt hat (z. B. auf Discord):',
        'fr': "Colle le code de profil que quelqu'un t'a envoyé (ex. sur Discord) :",
        'pt': 'Cole o código de perfil que alguém te enviou (ex.: pelo Discord):',
    },
    'import.confirm': {
        'sk': 'Importovať',
        'en': 'Import',
        'ja': 'インポート',
        'zh': '导入',
        'ru': 'Импортировать',
        'es': 'Importar',
        'de': 'Importieren',
        'fr': 'Importer',
        'pt': 'Importar',
    },
    'import.error': {
        'sk': 'Neplatný kód profilu: {err}',
        'en': 'Invalid profile code: {err}',
        'ja': '無効なプロファイルコードです: {err}',
        'zh': '无效的配置代码：{err}',
        'ru': 'Неверный код профиля: {err}',
        'es': 'Código de perfil inválido: {err}',
        'de': 'Ungültiger Profilcode: {err}',
        'fr': 'Code de profil invalide : {err}',
        'pt': 'Código de perfil inválido: {err}',
    },
    'import.invalid_format': {
        'sk': "chýbajúce alebo neplatné pole 'slots'",
        'en': "missing or invalid 'slots' field",
        'ja': '「slots」フィールドが欠けているか無効です',
        'zh': "缺少或无效的 'slots' 字段",
        'ru': "отсутствует или неверно поле 'slots'",
        'es': "campo 'slots' ausente o inválido",
        'de': "Feld 'slots' fehlt oder ist ungültig",
        'fr': "champ 'slots' manquant ou invalide",
        'pt': "campo 'slots' ausente ou inválido",
    },
    'import.default_name': {
        'sk': 'Importovaný profil',
        'en': 'Imported profile',
        'ja': 'インポートされたプロファイル',
        'zh': '已导入的配置文件',
        'ru': 'Импортированный профиль',
        'es': 'Perfil importado',
        'de': 'Importiertes Profil',
        'fr': 'Profil importé',
        'pt': 'Perfil importado',
    },
    'settings.auto_profile': {
        'sk': 'Pri známej hre sama prepnem profil a spustím sledovanie',
        'en': 'When a game I know is running, I switch the profile and start watching by myself',
        'ja': '知っているゲームが動いていたら、自分でプロファイルを切り替えて見守りを始める',
        'zh': '遇到我认识的游戏时，我会自己切换配置文件并开始关注',
        'ru': 'При знакомой игре сама переключу профиль и начну наблюдение',
        'es': 'Con un juego que conozco, cambio de perfil y empiezo a observar yo sola',
        'de': 'Bei einem Spiel, das ich kenne, wechsle ich selbst das Profil und starte die Beobachtung',
        'fr': 'Avec un jeu que je connais, je change de profil et je lance l’observation toute seule',
        'pt': 'Com um jogo que eu conheço, troco de perfil e começo a observar sozinha',
    },
    'settings.auto_profile_unavailable': {
        'sk': "Automatická detekcia hry (chýba knižnica 'psutil')",
        'en': "Auto game detection (missing 'psutil' library)",
        'ja': "ゲーム自動検出（'psutil' ライブラリが必要）",
        'zh': "自动识别游戏（缺少 'psutil' 库）",
        'ru': "Автоопределение игры (отсутствует библиотека 'psutil')",
        'es': "Detección automática de juegos (falta la librería 'psutil')",
        'de': "Automatische Spielerkennung (Bibliothek 'psutil' fehlt)",
        'fr': "Détection automatique du jeu (bibliothèque 'psutil' manquante)",
        'pt': "Detecção automática de jogo (biblioteca 'psutil' ausente)",
    },
    'overlay.dialog_title': {
        'sk': 'Obrázky v hre',
        'en': 'In-game pictures',
        'ja': 'ゲーム中の画像',
        'zh': '游戏中的图片',
        'ru': 'Картинки в игре',
        'es': 'Imágenes en el juego',
        'de': 'Bilder im Spiel',
        'fr': 'Images en jeu',
        'pt': 'Imagens no jogo',
    },
    'overlay.dialog_hint': {
        'sk': 'Pre každú pripomienku nastav, či ukáže obrázok v hre, aký veľký a kde na obrazovke. „Ukázať“ ho zobrazí a nechá na obrazovke — chyť ho myšou a potiahni, kam chceš; ďalším klikom polohu uložíš.',
        'en': 'For each cue, choose whether it shows its picture in-game, how big, and where on screen. “Show” displays it and keeps it on screen — grab it with the mouse and drag it wherever you want; click again to save the position.',
        'ja': '合図ごとに、ゲーム中に画像を出すか、その大きさと画面上の位置を設定します。「表示」で画像を出したままにできます — マウスでつかんで好きな場所へドラッグし、もう一度クリックすると位置が保存されます。',
        'zh': '为每条提示选择是否在游戏中显示图片，以及它的大小和屏幕位置。点击“显示”后它会一直留在屏幕上——用鼠标拖到任意位置，再点一次即可保存位置。',
        'ru': 'Для каждой подсказки выбери, показывать ли картинку в игре, какого размера и где на экране. «Показать» выводит её и оставляет на экране — схвати её мышью и перетащи куда хочешь; повторное нажатие сохранит положение.',
        'es': 'Para cada aviso, elige si muestra su imagen en el juego, de qué tamaño y dónde en la pantalla. «Mostrar» la enseña y la deja en pantalla: agárrala con el ratón y arrástrala donde quieras; vuelve a pulsar para guardar la posición.',
        'de': 'Wähle für jeden Hinweis, ob er sein Bild im Spiel zeigt, wie groß und wo auf dem Bildschirm. „Zeigen“ blendet es ein und lässt es stehen — greif es mit der Maus und zieh es, wohin du willst; ein weiterer Klick speichert die Position.',
        'fr': 'Pour chaque rappel, choisis s’il affiche son image en jeu, à quelle taille et où à l’écran. « Afficher » la montre et la laisse à l’écran — attrape-la à la souris et fais-la glisser où tu veux ; un nouveau clic enregistre la position.',
        'pt': 'Para cada aviso, escolha se ele mostra a imagem no jogo, de que tamanho e onde na tela. “Mostrar” a exibe e a mantém na tela — pegue-a com o mouse e arraste para onde quiser; clique de novo para salvar a posição.',
    },
    'overlay.slot.0': {
        'sk': 'Ťažisko',
        'en': 'Grounding',
        'ja': '重心',
        'zh': '重心',
        'ru': 'Опора',
        'es': 'Centro',
        'de': 'Erdung',
        'fr': 'Ancrage',
        'pt': 'Centro',
    },
    'overlay.slot.1': {
        'sk': 'Čeľusť',
        'en': 'Jaw',
        'ja': '顎',
        'zh': '下颌',
        'ru': 'Челюсть',
        'es': 'Mandíbula',
        'de': 'Kiefer',
        'fr': 'Mâchoire',
        'pt': 'Mandíbula',
    },
    'overlay.slot.2': {
        'sk': 'Ruka a pohľad',
        'en': 'Grip & gaze',
        'ja': '手と視線',
        'zh': '手与视线',
        'ru': 'Рука и взгляд',
        'es': 'Mano y mirada',
        'de': 'Hand und Blick',
        'fr': 'Main et regard',
        'pt': 'Mão e olhar',
    },
    # The cycle is no longer fixed (see overlay.breath_seconds below), hence
    # no "20 s" - the exact length is visible right in the sliders under
    # this heading.
    'overlay.slot.3': {
        'sk': 'Dych',
        'en': 'Breath',
        'ja': '呼吸',
        'zh': '呼吸',
        'ru': 'Дыхание',
        'es': 'Respiración',
        'de': 'Atem',
        'fr': 'Respiration',
        'pt': 'Respiração',
    },
    'overlay.enable': {
        'sk': 'Zobraziť v hre',
        'en': 'Show in-game',
        'ja': 'ゲーム内に表示',
        'zh': '在游戏内显示',
        'ru': 'Показывать в игре',
        'es': 'Mostrar en el juego',
        'de': 'Im Spiel anzeigen',
        'fr': 'Afficher en jeu',
        'pt': 'Mostrar no jogo',
    },
    'overlay.scale': {
        'sk': 'Veľkosť',
        'en': 'Size',
        'ja': 'サイズ',
        'zh': '大小',
        'ru': 'Размер',
        'es': 'Tamaño',
        'de': 'Größe',
        'fr': 'Taille',
        'pt': 'Tamanho',
    },
    'overlay.position': {
        'sk': 'Poloha na obrazovke',
        'en': 'Screen position',
        'ja': '画面上の位置',
        'zh': '屏幕位置',
        'ru': 'Положение на экране',
        'es': 'Posición en pantalla',
        'de': 'Bildschirmposition',
        'fr': "Position à l'écran",
        'pt': 'Posição na tela',
    },
    'overlay.test': {
        'sk': '▶ Ukázať',
        'en': '▶ Show',
        'ja': '▶ 表示',
        'zh': '▶ 显示',
        'ru': '▶ Показать',
        'es': '▶ Mostrar',
        'de': '▶ Zeigen',
        'fr': '▶ Afficher',
        'pt': '▶ Mostrar',
    },
    'log.auto_profile_created': {
        'sk': 'Spoznala som hru „{name}“ — založila som pre ňu nový profil s predvolenými pripomienkami.',
        'en': 'I recognised the game “{name}” — created a new profile for it with the default cues.',
        'ja': 'ゲーム「{name}」を見つけました — 既定の合図で新しいプロファイルを作りました。',
        'zh': '我认出了游戏“{name}”——已为它创建了带默认提示的新配置文件。',
        'ru': 'Я узнала игру «{name}» — создала для неё новый профиль с подсказками по умолчанию.',
        'es': 'He reconocido el juego «{name}»: le he creado un perfil nuevo con los avisos predeterminados.',
        'de': 'Ich habe das Spiel „{name}“ erkannt — ein neues Profil mit den Standard-Hinweisen angelegt.',
        'fr': 'J’ai reconnu le jeu « {name} » — je lui ai créé un nouveau profil avec les rappels par défaut.',
        'pt': 'Reconheci o jogo “{name}” — criei um novo perfil para ele com os avisos padrão.',
    },
    'log.auto_profile_detected': {
        'sk': 'Spoznala som hru „{name}“ — prepla som na jej profil a spustila sledovanie.',
        'en': 'I recognised the game “{name}” — switched to its profile and started watching.',
        'ja': 'ゲーム「{name}」を見つけました — そのプロファイルに切り替えて見守りを始めました。',
        'zh': '我认出了游戏“{name}”——已切换到它的配置文件并开始关注。',
        'ru': 'Я узнала игру «{name}» — переключилась на её профиль и начала наблюдение.',
        'es': 'He reconocido el juego «{name}»: he cambiado a su perfil y he empezado a observar.',
        'de': 'Ich habe das Spiel „{name}“ erkannt — zu seinem Profil gewechselt und die Beobachtung gestartet.',
        'fr': 'J’ai reconnu le jeu « {name} » — je suis passée à son profil et j’ai lancé l’observation.',
        'pt': 'Reconheci o jogo “{name}” — troquei para o perfil dele e comecei a observar.',
    },
    'log.auto_profile_ended': {
        'sk': 'Hra už nebeží — zastavila som sledovanie, ktoré som spustila sama.',
        'en': 'The game is no longer running — I stopped the watching I had started myself.',
        'ja': 'ゲームはもう動いていません — 自分で始めた見守りを止めました。',
        'zh': '游戏已经不在运行了——我停止了自己开始的关注。',
        'ru': 'Игра больше не запущена — я остановила наблюдение, которое запустила сама.',
        'es': 'El juego ya no está abierto: he detenido la observación que había iniciado yo.',
        'de': 'Das Spiel läuft nicht mehr — ich habe die Beobachtung gestoppt, die ich selbst gestartet hatte.',
        'fr': 'Le jeu ne tourne plus — j’ai arrêté l’observation que j’avais lancée moi-même.',
        'pt': 'O jogo não está mais rodando — parei a observação que eu mesma tinha iniciado.',
    },
    'log.auto_profile_on': {
        'sk': 'Automatické rozpoznávanie hry zapnuté.',
        'en': 'Automatic game detection turned on.',
        'ja': 'ゲームの自動検出をオンにしました。',
        'zh': '自动识别游戏已开启。',
        'ru': 'Автоопределение игры включено.',
        'es': 'Detección automática de juegos activada.',
        'de': 'Automatische Spielerkennung aktiviert.',
        'fr': 'Détection automatique du jeu activée.',
        'pt': 'Detecção automática de jogo ativada.',
    },
    'log.auto_profile_off': {
        'sk': 'Automatické rozpoznávanie hry vypnuté.',
        'en': 'Automatic game detection turned off.',
        'ja': 'ゲームの自動検出をオフにしました。',
        'zh': '自动识别游戏已关闭。',
        'ru': 'Автоопределение игры отключено.',
        'es': 'Detección automática de juegos desactivada.',
        'de': 'Automatische Spielerkennung deaktiviert.',
        'fr': 'Détection automatique du jeu désactivée.',
        'pt': 'Detecção automática de jogo desativada.',
    },
    'settings.hr_section_title': {
        'sk': 'Senzor tepu (Wi-Fi)',
        'en': 'Heart Rate Sensor (Wi-Fi)',
        'ja': '心拍センサー（Wi-Fi）',
        'zh': '心率传感器（Wi-Fi）',
        'ru': 'Датчик пульса (Wi-Fi)',
        'es': 'Sensor de ritmo cardíaco (Wi-Fi)',
        'de': 'Herzfrequenzsensor (Wi-Fi)',
        'fr': 'Capteur de fréquence cardiaque (Wi-Fi)',
        'pt': 'Sensor de frequência cardíaca (Wi-Fi)',
    },
    # 0.3: "(advanced)" - the field is not an address for the phone. As
    # "IP address" it tempted people to type 0.0.0.0 into the phone (audit).
    'settings.hr_ip_label': {
        'sk': 'Sieťová adresa (pokročilé)',
        'en': 'Network address (advanced)',
        'ja': 'ネットワークアドレス（上級）',
        'zh': '网络地址（高级）',
        'ru': 'Сетевой адрес (дополнительно)',
        'es': 'Dirección de red (avanzado)',
        'de': 'Netzwerkadresse (erweitert)',
        'fr': 'Adresse réseau (avancé)',
        'pt': 'Endereço de rede (avançado)',
    },
    'settings.hr_port_label': {
        'sk': 'Port',
        'en': 'Port',
        'ja': 'ポート',
        'zh': '端口',
        'ru': 'Порт',
        'es': 'Puerto',
        'de': 'Port',
        'fr': 'Port',
        'pt': 'Porta',
    },
    'settings.hr_port_hint': {
        'sk': 'Nechaj 4455 — to isté číslo zadáš v appke v telefóne.',
        'en': 'Leave 4455 — you enter the same number in the phone app.',
        'ja': '4455 のままで — 同じ番号を電話のアプリに入力します。',
        'zh': '保留 4455——在手机应用里输入同样的号码。',
        'ru': 'Оставь 4455 — то же число ты введёшь в приложении на телефоне.',
        'es': 'Deja 4455: el mismo número lo pones en la app del móvil.',
        'de': 'Lass 4455 stehen — dieselbe Zahl gibst du in der Handy-App ein.',
        'fr': 'Laisse 4455 — tu saisis le même numéro dans l’app du téléphone.',
        'pt': 'Deixe 4455 — o mesmo número você coloca no app do celular.',
    },
    'settings.hr_enable_switch': {
        'sk': 'Prijímať tep z telefónu',
        'en': 'Receive heart rate from the phone',
        'ja': '電話から心拍を受け取る',
        'zh': '接收手机发来的心率',
        'ru': 'Принимать пульс с телефона',
        'es': 'Recibir el pulso del móvil',
        'de': 'Puls vom Handy empfangen',
        'fr': 'Recevoir le pouls du téléphone',
        'pt': 'Receber o pulso do celular',
    },
    'settings.hr_status_disconnected': {
        'sk': 'Odpojené',
        'en': 'Disconnected',
        'ja': '切断されました',
        'zh': '已断开',
        'ru': 'Отключено',
        'es': 'Desconectado',
        'de': 'Getrennt',
        'fr': 'Déconnecté',
        'pt': 'Desconectado',
    },
    'settings.hr_status_connecting': {
        'sk': 'Pripája sa...',
        'en': 'Connecting...',
        'ja': '接続中...',
        'zh': '正在连接...',
        'ru': 'Подключение...',
        'es': 'Conectando...',
        'de': 'Verbindung wird hergestellt...',
        'fr': 'Connexion en cours...',
        'pt': 'Conectando...',
    },
    # State "linked": the TCP connection is held by the app on the PHONE,
    # the watch may not be sending anything yet (0.3 batch 4b) - hence
    # phone, not watch.
    'settings.hr_status_waiting': {
        'sk': 'Telefón pripojený — čakám na tep…',
        'en': 'Phone connected — waiting for heart rate…',
        'ja': '電話がつながりました — 心拍を待っています…',
        'zh': '手机已连接——正在等待心率…',
        'ru': 'Телефон подключён — жду пульс…',
        'es': 'Móvil conectado: esperando el pulso…',
        'de': 'Handy verbunden — ich warte auf den Puls…',
        'fr': 'Téléphone connecté — j’attends le pouls…',
        'pt': 'Celular conectado — esperando o pulso…',
    },
    'log.hr_client_connected': {
        'sk': 'Telefón sa pripojil. Ak tep aj tak nechodí, vyber v appke na telefóne scénu „Zanshin“ a zdroj „Tep“ — a over, či hodinky naozaj merajú.',
        'en': 'The phone connected. If no heart rate arrives anyway, pick the scene “Zanshin” and the source “Tep” in the phone app — and check that the watch is actually measuring.',
        'ja': '電話が接続しました。それでも心拍が届かなければ、電話のアプリでシーン「Zanshin」とソース「Tep」を選び、時計が本当に計測しているか確認してください。',
        'zh': '手机已连接。如果心率还是没过来，请在手机应用里选择场景“Zanshin”和来源“Tep”——并确认手表确实在测量。',
        'ru': 'Телефон подключился. Если пульс всё равно не приходит, выбери в приложении на телефоне сцену «Zanshin» и источник «Tep» — и проверь, что часы действительно измеряют.',
        'es': 'El móvil se ha conectado. Si aun así no llega el pulso, elige en la app del móvil la escena «Zanshin» y la fuente «Tep», y comprueba que el reloj esté midiendo de verdad.',
        'de': 'Das Handy ist verbunden. Kommt trotzdem kein Puls, wähl in der Handy-App die Szene „Zanshin“ und die Quelle „Tep“ — und prüf, ob die Uhr wirklich misst.',
        'fr': 'Le téléphone s’est connecté. Si le pouls n’arrive toujours pas, choisis dans l’app du téléphone la scène « Zanshin » et la source « Tep » — et vérifie que la montre mesure vraiment.',
        'pt': 'O celular se conectou. Se mesmo assim o pulso não chegar, escolha no app do celular a cena “Zanshin” e a fonte “Tep” — e confira se o relógio está mesmo medindo.',
    },
    'log.hr_client_gone': {
        'sk': 'Telefón sa odpojil.',
        'en': 'The phone disconnected.',
        'ja': '電話の接続が切れました。',
        'zh': '手机已断开连接。',
        'ru': 'Телефон отключился.',
        'es': 'El móvil se desconectó.',
        'de': 'Das Handy hat die Verbindung getrennt.',
        'fr': "Le téléphone s’est déconnecté.",
        'pt': 'O celular se desconectou.',
    },
    'log.hr_enabled': {
        'sk': 'Príjem tepu zapnutý — čakám na telefón ({ip}:{port}).',
        'en': 'Heart-rate receiving on — waiting for the phone ({ip}:{port}).',
        'ja': '心拍の受信をオンにしました — 電話を待っています（{ip}:{port}）。',
        'zh': '心率接收已开启——正在等待手机（{ip}:{port}）。',
        'ru': 'Приём пульса включён — жду телефон ({ip}:{port}).',
        'es': 'Recepción del pulso activada: espero al móvil ({ip}:{port}).',
        'de': 'Pulsempfang an — ich warte auf das Handy ({ip}:{port}).',
        'fr': 'Réception du pouls activée — j’attends le téléphone ({ip}:{port}).',
        'pt': 'Recepção do pulso ligada — esperando o celular ({ip}:{port}).',
    },
    'log.hr_disabled': {
        'sk': 'Príjem tepu vypnutý.',
        'en': 'Heart-rate receiving off.',
        'ja': '心拍の受信をオフにしました。',
        'zh': '心率接收已关闭。',
        'ru': 'Приём пульса выключен.',
        'es': 'Recepción del pulso desactivada.',
        'de': 'Pulsempfang aus.',
        'fr': 'Réception du pouls désactivée.',
        'pt': 'Recepção do pulso desligada.',
    },
    # 0.3: the sentence names a common cause (OBS with a WebSocket server on
    # 4455) and the fix that always works - another port. Changing the port
    # in the field restarts the sensor by itself after it has given up
    # (`on_hr_config_change`).
    'log.hr_port_busy': {
        'sk': 'Port {port} už používa iný program — často OBS so zapnutým WebSocket serverom alebo druhá kópia Zanshinu. Na stránke „{page}“ zmeň port (napr. na 4456) a rovnaké číslo zadaj v appke na telefóne.',
        'en': 'Port {port} is already used by another program — often OBS with its WebSocket server on, or a second copy of Zanshin. On the “{page}” page change the port (e.g. to 4456) and enter the same number in the phone app.',
        'ja': 'ポート {port} は既に別のプログラムが使用しています — 多くの場合、WebSocket サーバーをオンにした OBS か、Zanshin の2つ目のコピーです。「{page}」ページでポートを変更し（例: 4456）、スマホのアプリにも同じ番号を入力してください。',
        'zh': '端口 {port} 已被其他程序占用——通常是开启了 WebSocket 服务器的 OBS，或第二个 Zanshin 副本。请在“{page}”页面更改端口（例如改为 4456），并在手机应用中输入相同的号码。',
        'ru': 'Порт {port} уже занят другой программой — часто это OBS с включённым WebSocket-сервером или вторая копия Zanshin. На странице «{page}» смени порт (например, на 4456) и введи то же число в приложении на телефоне.',
        'es': 'El puerto {port} ya lo usa otro programa — a menudo OBS con su servidor WebSocket activado, o una segunda copia de Zanshin. En la página «{page}», cambia el puerto (por ejemplo, a 4456) y escribe el mismo número en la app del teléfono.',
        'de': 'Port {port} wird bereits von einem anderen Programm benutzt — oft OBS mit eingeschaltetem WebSocket-Server oder eine zweite Kopie von Zanshin. Ändere auf der Seite „{page}“ den Port (z. B. auf 4456) und gib dieselbe Zahl in der App auf dem Handy ein.',
        'fr': 'Le port {port} est déjà utilisé par un autre programme — souvent OBS avec son serveur WebSocket activé, ou une seconde copie de Zanshin. Sur la page « {page} », change le port (par ex. 4456) et saisis le même numéro dans l’app du téléphone.',
        'pt': 'A porta {port} já está em uso por outro programa — muitas vezes o OBS com o servidor WebSocket ligado, ou uma segunda cópia do Zanshin. Na página “{page}”, mude a porta (por exemplo, para 4456) e digite o mesmo número no app do celular.',
    },
    'log.hr_socket_error': {
        'sk': 'Príjem tepu sa nepodarilo spustiť (IP/port): {err}',
        'en': 'Couldn\'t start heart-rate receiving (IP/port): {err}',
        'ja': '心拍の受信を開始できませんでした（IP/ポート）: {err}',
        'zh': '心率接收启动失败（IP/端口）：{err}',
        'ru': 'Не удалось запустить приём пульса (IP/порт): {err}',
        'es': 'No se pudo iniciar la recepción del pulso (IP/puerto): {err}',
        'de': 'Pulsempfang konnte nicht gestartet werden (IP/Port): {err}',
        'fr': "Impossible de démarrer la réception du pouls (IP/port) : {err}",
        'pt': 'Não foi possível iniciar a recepção do pulso (IP/porta): {err}',
    },
    # No longer logged anywhere - the trigger from phase 1 (heart rate above
    # critical for 5 s -> breathing circle) has been deleted (app.py, B28).
    # Only the HUD illustration in the onboarding reads it (ui_dialogs.py,
    # step 3, slice [:40]) - hence a short true text that fits whole into 40
    # characters.
    'log.hr_breathing_triggered': {
        'sk': 'Tep {bpm} BPM — záťaž drží hore',
        'en': 'Heart rate {bpm} BPM — load holding up',
        'ja': '心拍 {bpm} BPM — 負荷が高いまま続いています',
        'zh': '心率 {bpm} BPM——负荷持续偏高',
        'ru': 'Пульс {bpm} BPM — нагрузка держится высокой',
        'es': 'Pulso {bpm} BPM — la carga se mantiene alta',
        'de': 'Puls {bpm} BPM — die Last bleibt oben',
        'fr': 'Pouls {bpm} BPM — la charge reste haute',
        'pt': 'Pulso {bpm} BPM — a carga se mantém alta',
    },
    'log.hr_bind_fallback': {
        'sk': 'Adresu {ip} toto PC nemá — tep preto prijímam na všetkých sieťach. Ak to funguje, pokojne si v poli nechaj 0.0.0.0.',
        'en': 'This PC doesn’t have the address {ip} — so I’m receiving heart rate on all networks instead. If it works, just leave 0.0.0.0 in the field.',
        'ja': 'この PC にはアドレス {ip} がありません — そのため、すべてのネットワークで心拍を受け取ります。うまくいけば、欄は 0.0.0.0 のままで大丈夫です。',
        'zh': '这台电脑没有地址 {ip}——所以我改为在所有网络上接收心率。如果这样能用，栏里留 0.0.0.0 就行。',
        'ru': 'У этого ПК нет адреса {ip} — поэтому принимаю пульс во всех сетях. Если так работает, спокойно оставь в поле 0.0.0.0.',
        'es': 'Este PC no tiene la dirección {ip}, así que recibo el pulso en todas las redes. Si funciona, deja 0.0.0.0 en el campo sin problema.',
        'de': 'Dieser PC hat die Adresse {ip} nicht — deshalb empfange ich den Puls in allen Netzwerken. Wenn es so klappt, lass einfach 0.0.0.0 im Feld stehen.',
        'fr': 'Ce PC n’a pas l’adresse {ip} — je reçois donc le pouls sur tous les réseaux. Si ça marche, laisse simplement 0.0.0.0 dans le champ.',
        'pt': 'Este PC não tem o endereço {ip} — por isso recebo o pulso em todas as redes. Se funcionar, pode deixar 0.0.0.0 no campo.',
    },
    'log.hr_overlay_disabled': {
        'sk': 'Na stránke „{page}“ máš vypnuté všetky obrázky — bez nich ti pripomienku nepošlem. Ak chceš, aby som sa ozývala, zapni si aspoň jeden.',
        'en': 'All in-game pictures are off on the “{page}” page — without them I can’t send you a cue. If you want me to speak up, turn at least one on.',
        'ja': '「{page}」ページで画像がすべてオフになっています — これでは合図を送れません。合図を出してほしければ、少なくとも1つをオンにしてください。',
        'zh': '“{page}”页面上的图片全都关掉了——这样我没法给你发提示。如果想让我提醒你，至少打开一个。',
        'ru': 'На странице «{page}» все картинки выключены — без них я не могу подать знак. Если хочешь, чтобы я подавала знаки, включи хотя бы одну.',
        'es': 'En la página «{page}» tienes todas las imágenes desactivadas: sin ellas no puedo avisarte. Si quieres que avise, activa al menos una.',
        'de': 'Auf der Seite „{page}“ sind alle Bilder aus — ohne sie kann ich dir keinen Hinweis schicken. Wenn ich mich melden soll, schalte mindestens eines ein.',
        'fr': 'Sur la page « {page} », toutes les images sont désactivées — sans elles, je ne peux pas t’envoyer de rappel. Si tu veux que je me manifeste, active-en au moins une.',
        'pt': 'Na página “{page}” todas as imagens estão desligadas — sem elas não consigo te mandar um aviso. Se quiser que eu avise, ligue pelo menos uma.',
    },
    'log.auto_profile_unavailable': {
        'sk': "Automatická detekcia hry nie je dostupná (chýba knižnica 'psutil'). Nainštaluj ju príkazom:  pip install psutil",
        'en': "Automatic game detection is unavailable (missing 'psutil' library). Install it with:  pip install psutil",
        'ja': "ゲームの自動検出は利用できません（'psutil' ライブラリが必要です）。次のコマンドでインストールしてください:  pip install psutil",
        'zh': "自动识别游戏功能不可用（缺少 'psutil' 库）。安装方法：  pip install psutil",
        'ru': "Автоопределение игры недоступно (отсутствует библиотека 'psutil'). Установи её командой:  pip install psutil",
        'es': "La detección automática de juegos no está disponible (falta la librería 'psutil'). Instálala con:  pip install psutil",
        'de': "Automatische Spielerkennung ist nicht verfügbar (Bibliothek 'psutil' fehlt). Installiere sie mit:  pip install psutil",
        'fr': "La détection automatique du jeu n'est pas disponible (bibliothèque 'psutil' manquante). Installe-la avec :  pip install psutil",
        'pt': "A detecção automática de jogo não está disponível (biblioteca 'psutil' ausente). Instale com:  pip install psutil",
    },
    # No longer "Anti-Cheat Safe Mode": only its maker can give a guarantee
    # about an anti-cheat, and "no blocking" was not true - the app registers
    # the "not now" shortcut (`hotkey.py`, RegisterHotKey), so the game does
    # not get that combination. The shortcut can be changed (or turned off)
    # in the settings file, so the sentence talks about the "not now"
    # shortcut and mentions Ctrl+Alt+Z only as the default.
    'log.safe_mode': {
        'sk': 'Ktoré klávesy stláčaš, nevidím — len kedy prišiel posledný vstup. Sama nič nestláčam. Jedinú skratku si rezervujem pre seba: „teraz nie“ (predvolene Ctrl+Alt+Z) — hra ju preto nedostane.',
        'en': 'I can’t see which keys you press — only when your last input came. I press nothing myself. I reserve one shortcut for myself: “not now” (Ctrl+Alt+Z by default) — so the game won’t get it.',
        'ja': 'どのキーを押しているかは見えません — 見えるのは最後の入力がいつだったかだけです。私からは何も押しません。自分用に予約しているショートカットは1つだけ：「今はいい」（既定は Ctrl+Alt+Z）— そのため、この組み合わせはゲームに届きません。',
        'zh': '我看不到你按了哪些键——只知道最后一次输入是什么时候。我自己不按任何键。我只为自己保留一个快捷键：“现在不要”（默认 Ctrl+Alt+Z）——所以游戏收不到这个组合键。',
        'ru': 'Какие клавиши ты нажимаешь, я не вижу — только когда был последний ввод. Сама я ничего не нажимаю. Для себя я резервирую одно сочетание: «не сейчас» (по умолчанию Ctrl+Alt+Z) — поэтому игра его не получит.',
        'es': 'No veo qué teclas pulsas, solo cuándo llegó tu última entrada. Yo no pulso nada. Me reservo un único atajo: «ahora no» (por defecto Ctrl+Alt+Z), así que el juego no lo recibe.',
        'de': 'Welche Tasten du drückst, sehe ich nicht — nur, wann die letzte Eingabe kam. Ich selbst drücke nichts. Ein Kürzel reserviere ich für mich: „jetzt nicht“ (standardmäßig Strg+Alt+Z) — das Spiel bekommt es deshalb nicht.',
        'fr': 'Je ne vois pas sur quelles touches tu appuies — seulement quand ta dernière saisie est arrivée. Moi, je n’appuie sur rien. Je me réserve un seul raccourci : « pas maintenant » (Ctrl+Alt+Z par défaut) — le jeu ne le reçoit donc pas.',
        'pt': 'Não vejo quais teclas você aperta — só quando chegou a sua última entrada. Eu mesma não aperto nada. Reservo um único atalho para mim: “agora não” (por padrão Ctrl+Alt+Z) — por isso o jogo não o recebe.',
    },
    'session.summary': {
        'sk': 'Relácia: Ťažisko {g}× | Čeľusť {j}× | Ruka a pohľad {r}× | Dych {b}×',
        'en': 'Session: Grounding {g}× | Jaw {j}× | Grip & gaze {r}× | Breath {b}×',
        'ja': 'セッション: 重心 {g}× | 顎 {j}× | 手と視線 {r}× | 呼吸 {b}×',
        'zh': '本局：重心 {g}次 | 下颌 {j}次 | 手与视线 {r}次 | 呼吸 {b}次',
        'ru': 'Сессия: Опора {g}× | Челюсть {j}× | Рука и взгляд {r}× | Дыхание {b}×',
        'es': 'Sesión: Centro {g}× | Mandíbula {j}× | Mano y mirada {r}× | Respiración {b}×',
        'de': 'Sitzung: Erdung {g}× | Kiefer {j}× | Hand und Blick {r}× | Atem {b}×',
        'fr': 'Séance : Ancrage {g}× | Mâchoire {j}× | Main et regard {r}× | Respiration {b}×',
        'pt': 'Sessão: Centro {g}× | Mandíbula {j}× | Mão e olhar {r}× | Respiração {b}×',
    },
    'slots.title': {
        'sk': 'Čo poviem',
        'en': 'What I say',
        'ja': '私が話すこと',
        'zh': '我会说什么',
        'ru': 'Что я скажу',
        'es': 'Qué digo',
        'de': 'Was ich sage',
        'fr': 'Ce que je dis',
        'pt': 'O que eu digo',
    },
    'slots.hint': {
        'sk': 'Kedy sa ozvem, rozhoduje tvoj tep: keď záťaž chvíľu drží hore, počkám na pauzu, v ktorej už nestúpa; v pásme Špička mlčím. Tu nastavíš, čo poviem.',
        'en': 'Your heart rate decides when I speak up: when your load holds up for a while, I wait for a pause in which it is no longer climbing; in the peak zone I stay quiet. Here you set what I say.',
        'ja': 'いつ合図を出すかは、あなたの心拍が決めます：負荷がしばらく高いまま続いたら、もう上がっていない合間を待ちます。「ピーク」ゾーンでは黙っています。ここでは、私が話す内容を設定します。',
        'zh': '什么时候提醒你，由你的心率决定：负荷持续偏高一阵子后，我会等它不再上升的停顿；在“高峰”区间我保持安静。这里设置的是我要说什么。',
        'ru': 'Когда подать знак, решает твой пульс: если нагрузка какое-то время держится высокой, я жду паузу, в которой она уже не растёт; в зоне «Пик» я молчу. Здесь ты задаёшь, что я скажу.',
        'es': 'Cuándo aviso lo decide tu pulso: si la carga se mantiene alta un rato, espero una pausa en la que ya no suba; en la zona Pico me callo. Aquí eliges qué digo.',
        'de': 'Wann ich mich melde, entscheidet dein Puls: Bleibt deine Last eine Weile oben, warte ich auf eine Pause, in der sie nicht mehr steigt; in der Zone Spitze schweige ich. Hier stellst du ein, was ich sage.',
        'fr': 'C’est ton pouls qui décide quand je me manifeste : si ta charge reste haute un moment, j’attends une pause où elle ne monte plus ; dans la zone Pic, je me tais. Ici, tu règles ce que je dis.',
        'pt': 'Quem decide quando eu aviso é o seu pulso: se a carga fica alta por um tempo, espero uma pausa em que ela já não esteja subindo; na zona Pico fico calada. Aqui você define o que eu digo.',
    },
    'mode.tts': {
        'sk': 'Hlas (TTS)',
        'en': 'Voice (TTS)',
        'ja': '音声 (TTS)',
        'zh': '语音（TTS）',
        'ru': 'Голос (TTS)',
        'es': 'Voz (TTS)',
        'de': 'Stimme (TTS)',
        'fr': 'Voix (TTS)',
        'pt': 'Voz (TTS)',
    },
    'mode.sfx': {
        'sk': 'Zvukový efekt (SFX)',
        'en': 'Sound effect (SFX)',
        'ja': '効果音 (SFX)',
        'zh': '音效（SFX）',
        'ru': 'Звуковой эффект (SFX)',
        'es': 'Efecto de sonido (SFX)',
        'de': 'Soundeffekt (SFX)',
        'fr': 'Effet sonore (SFX)',
        'pt': 'Efeito sonoro (SFX)',
    },
    'mode.combo': {
        'sk': 'Kombinácia (Hlas+SFX)',
        'en': 'Combo (Voice+SFX)',
        'ja': 'コンビネーション (音声+SFX)',
        'zh': '组合（语音+音效）',
        'ru': 'Комбо (Голос+SFX)',
        'es': 'Combo (Voz+SFX)',
        'de': 'Kombo (Stimme+SFX)',
        'fr': 'Combo (Voix+SFX)',
        'pt': 'Combo (Voz+SFX)',
    },
    'common.test': {
        'sk': '▶ Test',
        'en': '▶ Test',
        'ja': '▶ テスト',
        'zh': '▶ 测试',
        'ru': '▶ Тест',
        'es': '▶ Probar',
        'de': '▶ Testen',
        'fr': '▶ Tester',
        'pt': '▶ Testar',
    },
    'common.edit': {
        'sk': '⚙',
        'en': '⚙',
        'ja': '⚙',
        'zh': '⚙',
        'ru': '⚙',
        'es': '⚙',
        'de': '⚙',
        'fr': '⚙',
        'pt': '⚙',
    },
    'common.save': {
        'sk': 'Uložiť',
        'en': 'Save',
        'ja': '保存',
        'zh': '保存',
        'ru': 'Сохранить',
        'es': 'Guardar',
        'de': 'Speichern',
        'fr': 'Enregistrer',
        'pt': 'Salvar',
    },
    'common.cancel': {
        'sk': 'Zrušiť',
        'en': 'Cancel',
        'ja': 'キャンセル',
        'zh': '取消',
        'ru': 'Отмена',
        'es': 'Cancelar',
        'de': 'Abbrechen',
        'fr': 'Annuler',
        'pt': 'Cancelar',
    },
    'common.close': {
        'sk': 'Zavrieť',
        'en': 'Close',
        'ja': '閉じる',
        'zh': '关闭',
        'ru': 'Закрыть',
        'es': 'Cerrar',
        'de': 'Schließen',
        'fr': 'Fermer',
        'pt': 'Fechar',
    },
    'common.prepare_voices': {
        'sk': 'Pripraviť hlas pripomienok',
        'en': 'Prepare the cue voice',
        'ja': '合図の音声を準備',
        'zh': '准备提示语音',
        'ru': 'Подготовить голос подсказок',
        'es': 'Preparar la voz de los avisos',
        'de': 'Stimme der Hinweise vorbereiten',
        'fr': 'Préparer la voix des rappels',
        'pt': 'Preparar a voz dos avisos',
    },
    'common.minimize': {
        'sk': 'Minimalizovať do lišty',
        'en': 'Minimize to tray',
        'ja': 'トレイに最小化',
        'zh': '最小化到托盘',
        'ru': 'Свернуть в трей',
        'es': 'Minimizar a la bandeja',
        'de': 'In die Taskleiste minimieren',
        'fr': 'Réduire dans la barre système',
        'pt': 'Minimizar para a bandeja',
    },
    'common.log': {
        'sk': 'Denník',
        'en': 'Log',
        'ja': 'ログ',
        'zh': '日志',
        'ru': 'Журнал',
        'es': 'Registro',
        'de': 'Protokoll',
        'fr': 'Journal',
        'pt': 'Registro',
    },
    'slot.text_placeholder': {
        'sk': 'Čo zaznie (napr. Grounded)…',
        'en': 'What I say (e.g. Grounded)…',
        'ja': '話す言葉（例：Grounded）…',
        'zh': '要说的话（例如 Grounded）…',
        'ru': 'Что прозвучит (например, Grounded)…',
        'es': 'Qué digo (p. ej., Grounded)…',
        'de': 'Was ich sage (z. B. Grounded)…',
        'fr': 'Ce que je dis (par ex. Grounded)…',
        'pt': 'O que eu digo (por ex., Grounded)…',
    },
    'log.gamepad_connected': {
        'sk': 'Gamepad pripojený: {name}',
        'en': 'Gamepad connected: {name}',
        'ja': 'ゲームパッド接続: {name}',
        'zh': '手柄已连接：{name}',
        'ru': 'Геймпад подключён: {name}',
        'es': 'Mando conectado: {name}',
        'de': 'Gamepad verbunden: {name}',
        'fr': 'Manette connectée : {name}',
        'pt': 'Controle conectado: {name}',
    },
    'log.gamepad_disconnected': {
        'sk': 'Gamepad odpojený.',
        'en': 'Gamepad disconnected.',
        'ja': 'ゲームパッドが切断されました。',
        'zh': '手柄已断开连接。',
        'ru': 'Геймпад отключён.',
        'es': 'Mando desconectado.',
        'de': 'Gamepad getrennt.',
        'fr': 'Manette déconnectée.',
        'pt': 'Controle desconectado.',
    },
    'sfx.auto': {
        'sk': 'Automaticky (podľa témy)',
        'en': 'Automatic (matches theme)',
        'ja': '自動（テーマに合わせる）',
        'zh': '自动（匹配主题）',
        'ru': 'Автоматически (соответствует теме)',
        'es': 'Automático (según el tema)',
        'de': 'Automatisch (passend zum Theme)',
        'fr': 'Automatique (selon le thème)',
        'pt': 'Automático (conforme o tema)',
    },
    'sfx.custom_prefix': {
        'sk': 'Vlastný súbor: {name}',
        'en': 'Custom file: {name}',
        'ja': 'カスタムファイル: {name}',
        'zh': '自定义文件：{name}',
        'ru': 'Свой файл: {name}',
        'es': 'Archivo personalizado: {name}',
        'de': 'Eigene Datei: {name}',
        'fr': 'Fichier personnalisé : {name}',
        'pt': 'Arquivo personalizado: {name}',
    },
    'pack.zen': {
        'sk': 'Sumi',
        'en': 'Sumi',
        'ja': 'Sumi',
        'zh': 'Sumi',
        'ru': 'Sumi',
        'es': 'Sumi',
        'de': 'Sumi',
        'fr': 'Sumi',
        'pt': 'Sumi',
    },
    'pack.modern': {
        'sk': 'Aizome',
        'en': 'Aizome',
        'ja': 'Aizome',
        'zh': 'Aizome',
        'ru': 'Aizome',
        'es': 'Aizome',
        'de': 'Aizome',
        'fr': 'Aizome',
        'pt': 'Aizome',
    },
    'dialog.slot_settings_title': {
        'sk': 'Pripomienka {n} — podrobnosti',
        'en': 'Cue {n} — details',
        'ja': '合図 {n} — 詳細',
        'zh': '提示 {n}——详细设置',
        'ru': 'Подсказка {n} — подробности',
        'es': 'Aviso {n}: detalles',
        'de': 'Hinweis {n} — Details',
        'fr': 'Rappel {n} — détails',
        'pt': 'Aviso {n} — detalhes',
    },
    'dialog.voice_label': {
        'sk': 'Hlas tejto pripomienky:',
        'en': 'Voice for this cue:',
        'ja': 'この合図の音声：',
        'zh': '这条提示的语音：',
        'ru': 'Голос этой подсказки:',
        'es': 'Voz de este aviso:',
        'de': 'Stimme dieses Hinweises:',
        'fr': 'Voix de ce rappel :',
        'pt': 'Voz deste aviso:',
    },
    'dialog.voice_note': {
        'sk': 'Kedy sa ozvem, riadi záťaž tela — nie je to nastavenie, prah si počítam z tvojich relácií. S čím práve počítam, vidíš hore na stránke Pripomienky.',
        'en': 'When I speak up is driven by your body’s load — it isn’t a setting; I compute the threshold from your sessions. What I’m using right now is shown at the top of the Cues page.',
        'ja': 'いつ合図を出すかは体の負荷で決まります — 設定ではありません。しきい値はあなたのセッションから算出します。今使っている数値は「合図」ページの上に表示されます。',
        'zh': '什么时候提醒你，取决于身体的负荷——这不是设置；阈值是我根据你的记录算出来的。我现在用的数值显示在“提示”页面顶部。',
        'ru': 'Когда я подаю знак, зависит от нагрузки тела — это не настройка, порог я вычисляю по твоим сессиям. С чем я сейчас считаю, видно вверху страницы «Подсказки».',
        'es': 'Cuándo aviso depende de la carga de tu cuerpo: no es un ajuste; el umbral lo calculo a partir de tus sesiones. Lo que uso ahora mismo se ve arriba en la página Avisos.',
        'de': 'Wann ich mich melde, bestimmt die Last deines Körpers — das ist keine Einstellung; die Schwelle berechne ich aus deinen Sitzungen. Womit ich gerade rechne, steht oben auf der Seite Hinweise.',
        'fr': 'Quand je me manifeste dépend de la charge de ton corps — ce n’est pas un réglage ; je calcule le seuil à partir de tes séances. Ce que j’utilise en ce moment est affiché en haut de la page Rappels.',
        'pt': 'Quando eu aviso depende da carga do seu corpo — não é uma configuração; o limiar eu calculo a partir das suas sessões. O que estou usando agora aparece no topo da página Avisos.',
    },
    'dialog.voice_rec_label': {
        'sk': 'Vlastný hlas (nahrávka)',
        'en': 'Your own voice (recording)',
        'ja': '自分の声（録音）',
        'zh': '你自己的声音（录音）',
        'ru': 'Свой голос (запись)',
        'es': 'Tu propia voz (grabación)',
        'de': 'Eigene Stimme (Aufnahme)',
        'fr': 'Ta propre voix (enregistrement)',
        'pt': 'A sua própria voz (gravação)',
    },
    'dialog.voice_rec_none': {
        'sk': 'Žiadna — použije sa hlas (TTS).',
        'en': 'None — the voice (TTS) is used.',
        'ja': 'なし — 音声（TTS）を使用します。',
        'zh': '无——使用语音（TTS）。',
        'ru': 'Нет — используется голос (TTS).',
        'es': 'Ninguna — se usa la voz (TTS).',
        'de': 'Keine — es wird die Stimme (TTS) verwendet.',
        'fr': 'Aucune — la voix (TTS) est utilisée.',
        'pt': 'Nenhuma — é usada a voz (TTS).',
    },
    'dialog.voice_rec_set': {
        'sk': 'Nastavené: {name}',
        'en': 'Set: {name}',
        'ja': '設定済み：{name}',
        'zh': '已设置：{name}',
        'ru': 'Задано: {name}',
        'es': 'Establecido: {name}',
        'de': 'Gesetzt: {name}',
        'fr': 'Défini : {name}',
        'pt': 'Definido: {name}',
    },
    'dialog.voice_rec_record': {
        'sk': 'Nahrať',
        'en': 'Record',
        'ja': '録音',
        'zh': '录音',
        'ru': 'Записать',
        'es': 'Grabar',
        'de': 'Aufnehmen',
        'fr': 'Enregistrer',
        'pt': 'Gravar',
    },
    'dialog.voice_rec_file': {
        'sk': 'Zo súboru',
        'en': 'From file',
        'ja': 'ファイルから',
        'zh': '从文件',
        'ru': 'Из файла',
        'es': 'Desde archivo',
        'de': 'Aus Datei',
        'fr': 'Depuis un fichier',
        'pt': 'De um arquivo',
    },
    'dialog.voice_rec_clear': {
        'sk': 'Odstrániť',
        'en': 'Clear',
        'ja': '解除',
        'zh': '清除',
        'ru': 'Убрать',
        'es': 'Quitar',
        'de': 'Entfernen',
        'fr': 'Retirer',
        'pt': 'Remover',
    },
    'dialog.voice_rec_note': {
        'sk': 'Ak nahráš vlastný hlas, prehrá sa namiesto TTS — celý a čistý, bez filtra na kroky. Použije sa všade, kde by inak zaznel hlas.',
        'en': 'If you record your own voice, it plays instead of TTS — full and clean, without the footstep filter. Used wherever the voice would otherwise play.',
        'ja': '自分の声を録音すると、TTSの代わりに再生されます（足音フィルターなし、そのまま明瞭に）。本来ならTTSが話す場面すべてで使われます。',
        'zh': '录制你自己的声音后，会代替 TTS 播放——完整清晰，不经过脚步声滤波。凡是本应发声的地方都会使用它。',
        'ru': 'Если записать свой голос, он звучит вместо TTS — целиком и чисто, без фильтра шагов. Используется везде, где иначе прозвучал бы голос.',
        'es': 'Si grabas tu propia voz, se reproduce en vez del TTS — completa y limpia, sin el filtro de pasos. Se usa siempre que sonaría la voz.',
        'de': 'Wenn du deine eigene Stimme aufnimmst, wird sie statt TTS abgespielt — vollständig und klar, ohne den Schritte-Filter. Wird überall verwendet, wo sonst die Stimme erklänge.',
        'fr': 'Si tu enregistres ta propre voix, elle est jouée à la place du TTS — entière et nette, sans le filtre des pas. Utilisée partout où la voix retentirait sinon.',
        'pt': 'Se você gravar a sua própria voz, ela toca no lugar do TTS — inteira e limpa, sem o filtro de passos. É usada sempre que a voz tocaria.',
    },
    'dialog.choose_voice_title': {
        'sk': 'Zvukový súbor s hlasom pre pripomienku {n}',
        'en': 'Voice sound file for cue {n}',
        'ja': '合図 {n} の音声ファイル（声）',
        'zh': '提示 {n} 的语音文件',
        'ru': 'Звуковой файл голоса для подсказки {n}',
        'es': 'Archivo de voz para el aviso {n}',
        'de': 'Sprach-Audiodatei für Hinweis {n}',
        'fr': 'Fichier audio de voix pour le rappel {n}',
        'pt': 'Arquivo de áudio de voz para o aviso {n}',
    },
    'log.slot_voice_saved': {
        'sk': 'Pripomienka {n}: hlas = {voice}',
        'en': 'Cue {n}: voice = {voice}',
        'ja': '合図 {n}: 音声 = {voice}',
        'zh': '提示 {n}：语音 = {voice}',
        'ru': 'Подсказка {n}: голос = {voice}',
        'es': 'Aviso {n}: voz = {voice}',
        'de': 'Hinweis {n}: Stimme = {voice}',
        'fr': 'Rappel {n} : voix = {voice}',
        'pt': 'Aviso {n}: voz = {voice}',
    },
    'log.slot_voice_recorded': {
        'sk': 'Pripomienka {n}: vlastný hlas nahraný',
        'en': 'Cue {n}: own voice recorded',
        'ja': '合図 {n}: 自分の声を録音しました',
        'zh': '提示 {n}：已录制自己的声音',
        'ru': 'Подсказка {n}: свой голос записан',
        'es': 'Aviso {n}: voz propia grabada',
        'de': 'Hinweis {n}: eigene Stimme aufgenommen',
        'fr': 'Rappel {n} : voix propre enregistrée',
        'pt': 'Aviso {n}: voz própria gravada',
    },
    'log.slot_voice_set': {
        'sk': 'Pripomienka {n}: vlastný hlas zo súboru ({name})',
        'en': 'Cue {n}: own voice from file ({name})',
        'ja': '合図 {n}: ファイルから声を設定（{name}）',
        'zh': '提示 {n}：从文件设置声音（{name}）',
        'ru': 'Подсказка {n}: свой голос из файла ({name})',
        'es': 'Aviso {n}: voz propia desde archivo ({name})',
        'de': 'Hinweis {n}: eigene Stimme aus Datei ({name})',
        'fr': 'Rappel {n} : voix propre depuis un fichier ({name})',
        'pt': 'Aviso {n}: voz própria de um arquivo ({name})',
    },
    'log.slot_voice_cleared': {
        'sk': 'Pripomienka {n}: vlastný hlas zrušený — znova hovorí zvolený hlas',
        'en': 'Cue {n}: own voice cleared — the chosen voice speaks again',
        'ja': '合図 {n}: 自分の声を解除しました — 選んだ音声に戻ります',
        'zh': '提示 {n}：已清除自己的声音——改回所选的语音',
        'ru': 'Подсказка {n}: свой голос убран — снова говорит выбранный голос',
        'es': 'Aviso {n}: voz propia quitada: vuelve a hablar la voz elegida',
        'de': 'Hinweis {n}: eigene Stimme entfernt — es spricht wieder die gewählte Stimme',
        'fr': 'Rappel {n} : voix propre retirée — la voix choisie reprend',
        'pt': 'Aviso {n}: voz própria removida — volta a falar a voz escolhida',
    },
    'cue_rate.title': {
        'sk': 'Ako často sa ozvem',
        'en': 'How often I speak up',
        'ja': '話しかける頻度',
        'zh': '提示频率',
        'ru': 'Как часто я подаю голос',
        'es': 'Con qué frecuencia hablo',
        'de': 'Wie oft ich mich melde',
        'fr': 'À quelle fréquence je parle',
        'pt': 'Com que frequência eu falo',
    },
    'log.vizualy_napravene': {
        'sk': 'Zapla som obrázky v hre — bez aspoň jedného sa nemám ako ozvať. Vypnúť ich vieš na stránke „{page}“ v paneli „Obrázky v hre“.',
        'en': 'I turned the in-game pictures on — without at least one I can’t speak up at all. You can turn them off on the “{page}” page, in the “In-game pictures” panel.',
        'ja': 'ゲーム中の画像をオンにしました — 少なくとも1つないと、合図を出しようがありません。オフにするには「{page}」ページの「ゲーム中の画像」パネルで。',
        'zh': '我把游戏中的图片打开了——至少要有一个，我才能提醒你。可以在“{page}”页面的“游戏中的图片”面板里关掉它们。',
        'ru': 'Я включила картинки в игре — без хотя бы одной мне нечем подать знак. Выключить их можно на странице «{page}», в панели «Картинки в игре».',
        'es': 'He activado las imágenes en el juego: sin al menos una no tengo cómo avisarte. Puedes desactivarlas en la página «{page}», en el panel «Imágenes en el juego».',
        'de': 'Ich habe die Bilder im Spiel eingeschaltet — ohne mindestens eines kann ich mich gar nicht melden. Ausschalten kannst du sie auf der Seite „{page}“ im Bereich „Bilder im Spiel“.',
        'fr': 'J’ai activé les images en jeu — sans au moins une, je n’ai aucun moyen de me manifester. Tu peux les désactiver sur la page « {page} », dans le panneau « Images en jeu ».',
        'pt': 'Liguei as imagens no jogo — sem pelo menos uma não tenho como avisar. Você pode desligá-las na página “{page}”, no painel “Imagens no jogo”.',
    },
    'log.overlay_test_ukonceny': {
        'sk': 'Skryla som ukážku obrázka — kým je na obrazovke, zachytáva kliky myšou nad hrou.',
        'en': 'I hid the picture preview — while it’s on screen it catches mouse clicks over the game.',
        'ja': '画像のプレビューを隠しました — 表示中はゲーム上のマウスクリックを受け止めてしまいます。',
        'zh': '我把图片预览隐藏了——它显示时会拦截游戏上方的鼠标点击。',
        'ru': 'Я скрыла пробную картинку — пока она на экране, она перехватывает клики мышью над игрой.',
        'es': 'He ocultado la vista previa de la imagen: mientras está en pantalla, se queda con los clics del ratón sobre el juego.',
        'de': 'Ich habe die Bildvorschau ausgeblendet — solange sie zu sehen ist, fängt sie Mausklicks über dem Spiel ab.',
        'fr': 'J’ai masqué l’aperçu de l’image — tant qu’il est à l’écran, il capte les clics de souris au-dessus du jeu.',
        'pt': 'Escondi a prévia da imagem — enquanto está na tela, ela captura os cliques do mouse sobre o jogo.',
    },
    'palette.slot': {
        'sk': 'Pripomienka — {label}',
        'en': 'Cue — {label}',
        'ja': '合図 — {label}',
        'zh': '提示——{label}',
        'ru': 'Подсказка — {label}',
        'es': 'Aviso — {label}',
        'de': 'Hinweis — {label}',
        'fr': 'Rappel — {label}',
        'pt': 'Aviso — {label}',
    },
    'slots.unnamed': {
        'sk': 'Pripomienka {n}',
        'en': 'Cue {n}',
        'ja': '合図 {n}',
        'zh': '提示 {n}',
        'ru': 'Подсказка {n}',
        'es': 'Aviso {n}',
        'de': 'Hinweis {n}',
        'fr': 'Rappel {n}',
        'pt': 'Aviso {n}',
    },
    'kamae.no_watch': {
        'sk': 'Spustená, ale bez tepu',
        'en': 'Started, but no heart rate',
        'ja': '開始中ですが、心拍がありません',
        'zh': '已启动，但没有心率',
        'ru': 'Запущена, но пульса нет',
        'es': 'En marcha, pero sin pulso',
        'de': 'Gestartet, aber ohne Puls',
        'fr': 'Lancée, mais sans pouls',
        'pt': 'Iniciada, mas sem pulso',
    },
    # 0.3: points to the watch icon (turns reception on and opens the
    # pairing guide), not to the bare switch - without pairing the switch
    # would not help.
    'kamae.no_watch_sub': {
        'sk': 'Bez hodiniek neviem, kedy ti záťaž stúpa, tak mlčím. Spáruj ich — ikona hodiniek vľavo.',
        'en': 'Without a watch I can’t tell when your load rises, so I stay quiet. Pair it — the watch icon on the left.',
        'ja': '時計がないと負荷が上がったのがわからないので、黙っています。ペアリングして — 左の時計アイコンから。',
        'zh': '没有手表，我不知道你的负荷什么时候升高，所以保持安静。去配对吧——左侧的手表图标。',
        'ru': 'Без часов я не знаю, когда растёт твоя нагрузка, поэтому молчу. Подключи их — значок часов слева.',
        'es': 'Sin reloj no sé cuándo te sube la carga, así que me callo. Vincúlalo: el icono del reloj a la izquierda.',
        'de': 'Ohne Uhr weiß ich nicht, wann deine Last steigt, also schweige ich. Verbinde sie — das Uhr-Symbol links.',
        'fr': 'Sans montre, je ne sais pas quand ta charge monte, alors je me tais. Connecte-la — l’icône de la montre à gauche.',
        'pt': 'Sem relógio, não sei quando a sua carga sobe, então fico calada. Pareie o relógio — o ícone do relógio à esquerda.',
    },
    # The sensor is LISTENING, but heart rate is not coming in (dropout,
    # busy port, nothing has connected yet). Distinct from `kamae.no_watch`,
    # which is a sensor turned off. In this state the bar used to falsely
    # claim "Watching your heart rate, waiting..." based only on the switch -
    # the biggest element of the window was telling an untruth (bug A2).
    'kamae.no_hr': {
        'sk': 'Čakám na tep',
        'en': 'Waiting for heart rate',
        'ja': 'Waiting for heart rate',
        'zh': 'Waiting for heart rate',
        'ru': 'Waiting for heart rate',
        'es': 'Waiting for heart rate',
        'de': 'Waiting for heart rate',
        'fr': 'Waiting for heart rate',
        'pt': 'Waiting for heart rate',
    },
    # 0.2: heart rate goes watch -> phone (Bluetooth) -> Wi-Fi -> computer,
    # not from the watch straight to Wi-Fi. Old translations
    # (_DOPLNENE_PREKLADY) deleted, so that the old wording does not survive
    # in any language; the new ones are from the languages phase.
    'kamae.no_hr_sub': {
        'sk': 'Príjem tepu je zapnutý, ale z hodiniek zatiaľ nič nechodí. Skontroluj, či hodinky merajú a sú pri telefóne (Bluetooth) a či je telefón na tej istej Wi‑Fi ako počítač.',
        'en': 'Heart-rate receiving is on, but nothing is coming from the watch yet. Check that the watch is measuring and near the phone (Bluetooth), and that the phone is on the same Wi‑Fi as the PC.',
        'ja': '心拍の受信はオンですが、時計からまだ何も届いていません。時計が計測していて電話の近くにあるか（Bluetooth）、電話が PC と同じ Wi‑Fi にあるか確認してください。',
        'zh': '心率接收已开启，但手表还没有发来任何数据。请检查手表是否在测量、是否在手机旁边（蓝牙），以及手机是否和电脑连在同一个 Wi‑Fi 上。',
        'ru': 'Приём пульса включён, но с часов пока ничего не приходит. Проверь, что часы измеряют и находятся рядом с телефоном (Bluetooth), а телефон — в той же сети Wi‑Fi, что и ПК.',
        'es': 'La recepción del pulso está activada, pero del reloj aún no llega nada. Comprueba que el reloj esté midiendo y cerca del móvil (Bluetooth), y que el móvil esté en el mismo Wi‑Fi que el PC.',
        'de': 'Der Pulsempfang ist an, aber von der Uhr kommt noch nichts. Prüf, ob die Uhr misst und beim Handy ist (Bluetooth) und ob das Handy im selben WLAN wie der PC ist.',
        'fr': 'La réception du pouls est activée, mais rien n’arrive encore de la montre. Vérifie que la montre mesure et qu’elle est près du téléphone (Bluetooth), et que le téléphone est sur le même Wi‑Fi que le PC.',
        'pt': 'A recepção do pulso está ligada, mas ainda não chega nada do relógio. Confira se o relógio está medindo e perto do celular (Bluetooth) e se o celular está no mesmo Wi‑Fi que o PC.',
    },
    # Reception is running, but nobody connected within ~20 s
    # (`_hr_no_client`). "Waiting for heart rate" would wait the whole
    # evening without advice - the cause is almost always in the network,
    # so the sentence says which one and where the steps are (0.3).
    'kamae.no_client': {
        'sk': 'Telefón sa nepripojil',
        'en': 'The phone didn’t connect',
        'ja': '電話がつながりませんでした',
        'zh': '手机没有连上',
        'ru': 'Телефон не подключился',
        'es': 'El móvil no se conectó',
        'de': 'Das Handy hat sich nicht verbunden',
        'fr': 'Le téléphone ne s’est pas connecté',
        'pt': 'O celular não se conectou',
    },
    'kamae.no_client_sub': {
        'sk': 'Najčastejšie ho zastaví firewall Windows, sieť nastavená ako Verejná alebo nová adresa PC po reštarte routera. Postup nájdeš v návode na párovanie — klikni na ikonu hodiniek vľavo.',
        'en': 'Most often it’s stopped by Windows Firewall, a network set to Public, or a new PC address after a router restart. The steps are in the pairing guide — click the watch icon on the left.',
        'ja': 'よくある原因は Windows ファイアウォール、「パブリック」に設定されたネットワーク、ルーターの再起動で変わった PC のアドレス。手順はペアリングのガイドにある — 左の時計アイコンをクリックして。',
        'zh': '最常见的原因是 Windows 防火墙、被设为“公用”的网络，或者路由器重启后电脑地址变了。步骤在配对指南里——点击左侧的手表图标。',
        'ru': 'Чаще всего мешает брандмауэр Windows, сеть с профилем «Общедоступная» или новый адрес ПК после перезапуска роутера. Что делать — в руководстве по подключению: нажми значок часов слева.',
        'es': 'Lo más habitual es que lo frene el firewall de Windows, una red configurada como Pública o una nueva dirección del PC tras reiniciar el router. Los pasos están en la guía de vinculación: haz clic en el icono del reloj a la izquierda.',
        'de': 'Meist blockiert die Windows-Firewall, ein als „Öffentlich“ eingestelltes Netzwerk oder eine neue PC-Adresse nach einem Router-Neustart. Die Schritte stehen in der Anleitung zum Verbinden — klick links auf das Uhr-Symbol.',
        'fr': 'Le plus souvent, c’est le pare-feu Windows, un réseau réglé sur Public ou une nouvelle adresse du PC après un redémarrage de la box. Les étapes sont dans le guide de connexion — clique sur l’icône de la montre à gauche.',
        'pt': 'Na maioria das vezes, o bloqueio vem do firewall do Windows, de uma rede definida como Pública ou de um novo endereço do PC depois de reiniciar o roteador. Os passos estão no guia de pareamento — clique no ícone do relógio à esquerda.',
    },
    'dev.min_gap_clamped': {
        'sk': 'Odstup som zdvihla na {s} s — nižšie by si dve pripomienky zneplatnili meracie okná.',
        'en': 'I raised the gap to {s} s — below that two cues invalidate each other’s measurement windows.',
        'ja': '間隔を {s} 秒に引き上げました。これより短いと、2つの合図が互いの測定窓を無効にしてしまいます。',
        'zh': '我把间隔提高到 {s} 秒——再短两条提示会互相作废测量窗口。',
        'ru': 'Я подняла интервал до {s} с — ниже две подсказки обнуляли бы измерительные окна друг друга.',
        'es': 'He subido el intervalo a {s} s — por debajo, dos avisos invalidarían mutuamente sus ventanas de medición.',
        'de': 'Ich habe den Abstand auf {s} s angehoben — darunter entwerten zwei Hinweise ihre Messfenster gegenseitig.',
        'fr': 'J’ai remonté l’écart à {s} s — en dessous, deux rappels invalideraient mutuellement leurs fenêtres de mesure.',
        'pt': 'Subi o intervalo para {s} s — abaixo disso, dois avisos invalidam as janelas de medição um do outro.',
    },
    'log.cue_skipped_all_off': {
        'sk': 'Chvíľa na pripomienku prišla, ale všetky sú vypnuté — mlčím.',
        'en': 'The moment for a cue came, but all of them are off — staying silent.',
        'ja': '合図を出す頃合いでしたが、合図はすべてオフなので黙っています。',
        'zh': '到了该出声的时候，但所有提示都已关闭——保持安静。',
        'ru': 'Момент для подсказки настал, но все подсказки выключены — молчу.',
        'es': 'Llegó el momento de un aviso, pero están todos apagados: me callo.',
        'de': 'Der Moment für einen Hinweis war da, aber alle sind aus — ich schweige.',
        'fr': "Le moment d'un rappel est venu, mais ils sont tous désactivés — je me tais.",
        'pt': 'Chegou o momento de um aviso, mas estão todos desligados — fico calada.',
    },
    # 0.3: without "it is usually a second copy of the app" - since 0.3 a
    # second copy does not get to the port (main.py, single instance). The
    # cause and the fix are only given by `log.hr_port_busy`, once the
    # attempts run out.
    'log.hr_port_busy_retry': {
        'sk': 'Port {port} drží iný program — skúšam znova ({n}/{z}).',
        'en': 'Port {port} is held by another program — retrying ({n}/{z}).',
        'ja': 'ポート {port} は別のプログラムが使用中です。再試行します（{n}/{z}）。',
        'zh': '端口 {port} 被其他程序占用——正在重试（{n}/{z}）。',
        'ru': 'Порт {port} занят другой программой — пробую снова ({n}/{z}).',
        'es': 'El puerto {port} lo tiene otro programa: reintentando ({n}/{z}).',
        'de': 'Port {port} ist von einem anderen Programm belegt — neuer Versuch ({n}/{z}).',
        'fr': "Le port {port} est occupé par un autre programme — nouvel essai ({n}/{z}).",
        'pt': 'A porta {port} está ocupada por outro programa — tentando de novo ({n}/{z}).',
    },
    'settings.hr_status_busy': {
        'sk': 'Port je obsadený — skúšam znova',
        'en': 'Port is busy — retrying',
        'ja': 'ポート使用中 — 再試行中',
        'zh': '端口被占用——正在重试',
        'ru': 'Порт занят — пробую снова',
        'es': 'Puerto ocupado: reintentando',
        'de': 'Port belegt — neuer Versuch',
        'fr': 'Port occupé — nouvel essai',
        'pt': 'Porta ocupada — tentando de novo',
    },
    # We are listening, but nobody connected within ~20 s (most often a
    # firewall or a different Wi-Fi). A different problem from
    # "Connecting...", so it says so (B2).
    'settings.hr_status_no_client': {
        'sk': 'Príjem zapnutý — telefón sa zatiaľ nepripojil',
        'en': 'Receiving on — the phone hasn’t connected yet',
        'ja': '受信オン — 電話はまだ接続していません',
        'zh': '接收已开启——手机还没有连接',
        'ru': 'Приём включён — телефон ещё не подключился',
        'es': 'Recepción activada: el móvil aún no se ha conectado',
        'de': 'Empfang an — das Handy hat sich noch nicht verbunden',
        'fr': 'Réception activée — le téléphone ne s’est pas encore connecté',
        'pt': 'Recepção ligada — o celular ainda não se conectou',
    },
    # After the attempts are used up the sensor GIVES UP. Until now the state
    # stayed "busy" and the label forever claimed "retrying", although nobody
    # is trying any more (B3).
    'settings.hr_status_busy_gave_up': {
        'sk': 'Port je obsadený — senzor vypnutý',
        'en': 'Port is busy — sensor turned off',
        'ja': 'Port is busy — sensor turned off',
        'zh': 'Port is busy——sensor turned off',
        'ru': 'Port is busy — sensor turned off',
        'es': 'Port is busy — sensor turned off',
        'de': 'Port is busy — sensor turned off',
        'fr': 'Port is busy — sensor turned off',
        'pt': 'Port is busy — sensor turned off',
    },
    'session.context.supplement': {
        'sk': 'doplnok / pre-workout',
        'en': 'supplement / pre-workout',
        'ja': 'サプリ / プレワークアウト',
        'zh': '补剂 / 训练前补充剂',
        'ru': 'добавка / предтрен',
        'es': 'suplemento / pre-entreno',
        'de': 'Supplement / Pre-Workout',
        'fr': 'complément / pre-workout',
        'pt': 'suplemento / pré-treino',
    },
    'session.context.food': {
        'sk': 'jedlo pred hraním',
        'en': 'ate before playing',
        'ja': 'プレイ前に食事',
        'zh': '玩之前吃过东西',
        'ru': 'еда перед игрой',
        'es': 'comí antes de jugar',
        'de': 'vor dem Spielen gegessen',
        'fr': "j'ai mangé avant de jouer",
        'pt': 'comi antes de jogar',
    },
    'session.end.trace_hint': {
        'sk': 'Tep počas celej relácie. Trojuholníky sú pripomienky; tenký pruh ukazuje, kedy sa pravdepodobne hralo (klávesnica, myš alebo ovládač).',
        'en': 'Your heart rate across the whole session. Triangles are cues; the thin band shows when you were probably playing (keyboard, mouse or controller).',
        'ja': 'セッション全体の心拍。三角は合図、細い帯はおそらくプレイしていた時間（キーボード、マウス、コントローラー）を示します。',
        'zh': '整个记录期间的心率。三角形是提示；细条显示你大概在玩的时间（键盘、鼠标或手柄）。',
        'ru': 'Пульс за всю сессию. Треугольники — подсказки; тонкая полоса показывает, когда, вероятно, шла игра (клавиатура, мышь или контроллер).',
        'es': 'Tu pulso durante toda la sesión. Los triángulos son avisos; la franja fina muestra cuándo probablemente estabas jugando (teclado, ratón o mando).',
        'de': 'Dein Puls über die ganze Sitzung. Die Dreiecke sind Hinweise; der schmale Streifen zeigt, wann vermutlich gespielt wurde (Tastatur, Maus oder Controller).',
        'fr': 'Ton pouls sur toute la séance. Les triangles sont les rappels ; la fine bande montre quand tu jouais probablement (clavier, souris ou manette).',
        'pt': 'O seu pulso durante toda a sessão. Os triângulos são avisos; a faixa fina mostra quando você provavelmente estava jogando (teclado, mouse ou controle).',
    },
    'voice.global': {
        'sk': '(globálny hlas)',
        'en': '(global voice)',
        'ja': '（全体設定の音声）',
        'zh': '（全局语音）',
        'ru': '(глобальный голос)',
        'es': '(voz global)',
        'de': '(globale Stimme)',
        'fr': '(voix globale)',
        'pt': '(voz global)',
    },
    'dialog.choose_sfx_title': {
        'sk': 'Zvukový súbor pre pripomienku {n}',
        'en': 'Sound file for cue {n}',
        'ja': '合図 {n} の効果音ファイル',
        'zh': '提示 {n} 的音效文件',
        'ru': 'Звуковой файл для подсказки {n}',
        'es': 'Archivo de sonido para el aviso {n}',
        'de': 'Tondatei für Hinweis {n}',
        'fr': 'Fichier son pour le rappel {n}',
        'pt': 'Arquivo de som para o aviso {n}',
    },
    'filetype.audio': {
        'sk': 'Audio',
        'en': 'Audio',
        'ja': 'オーディオ',
        'zh': '音频',
        'ru': 'Аудио',
        'es': 'Audio',
        'de': 'Audio',
        'fr': 'Audio',
        'pt': 'Áudio',
    },
    'filetype.all': {
        'sk': 'Všetky súbory',
        'en': 'All files',
        'ja': 'すべてのファイル',
        'zh': '所有文件',
        'ru': 'Все файлы',
        'es': 'Todos los archivos',
        'de': 'Alle Dateien',
        'fr': 'Tous les fichiers',
        'pt': 'Todos os arquivos',
    },
    'record.title': {
        'sk': 'Nahrávka pre pripomienku {n}',
        'en': 'Recording for cue {n}',
        'ja': '合図 {n} の録音',
        'zh': '提示 {n} 的录音',
        'ru': 'Запись для подсказки {n}',
        'es': 'Grabación para el aviso {n}',
        'de': 'Aufnahme für Hinweis {n}',
        'fr': 'Enregistrement pour le rappel {n}',
        'pt': 'Gravação para o aviso {n}',
    },
    'record.hint': {
        'sk': 'Nahraj si vlastný hlas pripomienky alebo zvuk z mikrofónu.',
        'en': 'Record your own cue voice or a sound from the microphone.',
        'ja': 'マイクから、合図用の自分の声や音を録音します。',
        'zh': '用麦克风录下你自己的提示语音或声音。',
        'ru': 'Запиши с микрофона свой голос для подсказки или звук.',
        'es': 'Graba con el micrófono tu propia voz para el aviso o un sonido.',
        'de': 'Nimm mit dem Mikrofon deine eigene Stimme für den Hinweis oder einen Ton auf.',
        'fr': 'Enregistre au micro ta propre voix pour le rappel, ou un son.',
        'pt': 'Grave pelo microfone a sua própria voz para o aviso, ou um som.',
    },
    'record.ready': {
        'sk': 'Pripravené',
        'en': 'Ready',
        'ja': '準備完了',
        'zh': '就绪',
        'ru': 'Готово',
        'es': 'Listo',
        'de': 'Bereit',
        'fr': 'Prêt',
        'pt': 'Pronto',
    },
    'record.start': {
        'sk': '● Nahrávať',
        'en': '● Record',
        'ja': '● 録音',
        'zh': '● 录音',
        'ru': '● Запись',
        'es': '● Grabar',
        'de': '● Aufnehmen',
        'fr': '● Enregistrer',
        'pt': '● Gravar',
    },
    'record.stop': {
        'sk': '■ Stop a uložiť',
        'en': '■ Stop and save',
        'ja': '■ 停止して保存',
        'zh': '■ 停止并保存',
        'ru': '■ Остановить и сохранить',
        'es': '■ Detener y guardar',
        'de': '■ Stoppen und speichern',
        'fr': '■ Arrêter et enregistrer',
        'pt': '■ Parar e salvar',
    },
    'record.preview': {
        'sk': '▶ Prehrať',
        'en': '▶ Play',
        'ja': '▶ 再生',
        'zh': '▶ 播放',
        'ru': '▶ Воспроизвести',
        'es': '▶ Reproducir',
        'de': '▶ Abspielen',
        'fr': '▶ Lire',
        'pt': '▶ Reproduzir',
    },
    'record.exists': {
        'sk': 'Existuje: {name}',
        'en': 'Existing: {name}',
        'ja': '既存: {name}',
        'zh': '已存在：{name}',
        'ru': 'Существующий: {name}',
        'es': 'Existente: {name}',
        'de': 'Vorhanden: {name}',
        'fr': 'Existant : {name}',
        'pt': 'Existente: {name}',
    },
    'record.saved': {
        'sk': 'Uložené: {name}',
        'en': 'Saved: {name}',
        'ja': '保存済み: {name}',
        'zh': '已保存：{name}',
        'ru': 'Сохранено: {name}',
        'es': 'Guardado: {name}',
        'de': 'Gespeichert: {name}',
        'fr': 'Enregistré : {name}',
        'pt': 'Salvo: {name}',
    },
    'record.recording': {
        'sk': '● Nahrávam... {t} s',
        'en': '● Recording... {t} s',
        'ja': '● 録音中... {t} 秒',
        'zh': '● 录音中… {t} 秒',
        'ru': '● Запись... {t} с',
        'es': '● Grabando... {t} s',
        'de': '● Aufnahme läuft ... {t} s',
        'fr': '● Enregistrement... {t} s',
        'pt': '● Gravando... {t} s',
    },
    'record.save_error': {
        'sk': 'Nahrávku sa nepodarilo uložiť:\n{err}',
        'en': "Couldn't save the recording:\n{err}",
        'ja': '録音を保存できませんでした:\n{err}',
        'zh': '无法保存录音：\n{err}',
        'ru': 'Не удалось сохранить запись:\n{err}',
        'es': 'No se pudo guardar la grabación:\n{err}',
        'de': 'Aufnahme konnte nicht gespeichert werden:\n{err}',
        'fr': "Impossible d'enregistrer l'enregistrement :\n{err}",
        'pt': 'Não foi possível salvar a gravação:\n{err}',
    },
    'record.start_error': {
        'sk': 'Nahrávanie sa nepodarilo spustiť:\n{err}\n\nSkontroluj mikrofón a povolenia Windows.',
        'en': "Couldn't start recording:\n{err}\n\nCheck your microphone and Windows permissions.",
        'ja': '録音を開始できませんでした:\n{err}\n\nマイクとWindowsの権限を確認してください。',
        'zh': '无法开始录音：\n{err}\n\n请检查麦克风及 Windows 权限设置。',
        'ru': 'Не удалось начать запись:\n{err}\n\nПроверь микрофон и разрешения Windows.',
        'es': 'No se pudo iniciar la grabación:\n{err}\n\nRevisa el micrófono y los permisos de Windows.',
        'de': 'Aufnahme konnte nicht gestartet werden:\n{err}\n\nÜberprüfe Mikrofon und Windows-Berechtigungen.',
        'fr': "Impossible de démarrer l'enregistrement :\n{err}\n\nVérifie le micro et les autorisations Windows.",
        'pt': 'Não foi possível iniciar a gravação:\n{err}\n\nVerifique o microfone e as permissões do Windows.',
    },
    'settings.volume': {
        'sk': 'Hlasitosť:',
        'en': 'Volume:',
        'ja': '音量:',
        'zh': '音量：',
        'ru': 'Громкость:',
        'es': 'Volumen:',
        'de': 'Lautstärke:',
        'fr': 'Volume :',
        'pt': 'Volume:',
    },
    'settings.balance': {
        'sk': 'Vyváženie SFX ↔ Hlas:',
        'en': 'SFX ↔ Voice balance:',
        'ja': 'SFX ↔ 音声バランス:',
        'zh': '音效 ↔ 语音 平衡：',
        'ru': 'Баланс SFX ↔ Голос:',
        'es': 'Balance SFX ↔ Voz:',
        'de': 'SFX ↔ Stimme Balance:',
        'fr': 'Équilibre SFX ↔ Voix :',
        'pt': 'Equilíbrio SFX ↔ Voz:',
    },
    'settings.balance_center': {
        'sk': 'vyrovnané',
        'en': 'balanced',
        'ja': '均等',
        'zh': '均衡',
        'ru': 'сбалансировано',
        'es': 'equilibrado',
        'de': 'ausgewogen',
        'fr': 'équilibré',
        'pt': 'equilibrado',
    },
    'settings.balance_sfx': {
        'sk': 'SFX',
        'en': 'SFX',
        'ja': 'SFX',
        'zh': '音效',
        'ru': 'SFX',
        'es': 'SFX',
        'de': 'SFX',
        'fr': 'SFX',
        'pt': 'SFX',
    },
    'settings.balance_tts': {
        'sk': 'Hlas',
        'en': 'Voice',
        'ja': '音声',
        'zh': '语音',
        'ru': 'Голос',
        'es': 'Voz',
        'de': 'Stimme',
        'fr': 'Voix',
        'pt': 'Voz',
    },
    'settings.engine': {
        'sk': 'Zdroj hlasu',
        'en': 'Voice source',
        'ja': '音声の種類',
        'zh': '语音来源',
        'ru': 'Источник голоса',
        'es': 'Origen de la voz',
        'de': 'Stimmquelle',
        'fr': 'Source de la voix',
        'pt': 'Fonte da voz',
    },
    'settings.voice': {
        'sk': 'Globálny hlas:',
        'en': 'Global voice:',
        'ja': '全体音声:',
        'zh': '全局语音：',
        'ru': 'Глобальный голос:',
        'es': 'Voz global:',
        'de': 'Globale Stimme:',
        'fr': 'Voix globale :',
        'pt': 'Voz global:',
    },
    'settings.rate': {
        'sk': 'Rýchlosť:',
        'en': 'Speed:',
        'ja': '速度:',
        'zh': '语速：',
        'ru': 'Скорость:',
        'es': 'Velocidad:',
        'de': 'Geschwindigkeit:',
        'fr': 'Vitesse :',
        'pt': 'Velocidade:',
    },
    'engine.edge': {
        'sk': 'Prirodzený (online, Microsoft)',
        'en': 'Natural (online, Microsoft)',
        'ja': '自然な音声（オンライン、Microsoft）',
        'zh': '自然语音（联网，Microsoft）',
        'ru': 'Естественный (онлайн, Microsoft)',
        'es': 'Natural (en línea, Microsoft)',
        'de': 'Natürlich (online, Microsoft)',
        'fr': 'Naturelle (en ligne, Microsoft)',
        'pt': 'Natural (online, Microsoft)',
    },
    'engine.sapi': {
        'sk': 'Windows (bez internetu)',
        'en': 'Windows (offline)',
        'ja': 'Windows（オフライン）',
        'zh': 'Windows（离线）',
        'ru': 'Windows (без интернета)',
        'es': 'Windows (sin conexión)',
        'de': 'Windows (ohne Internet)',
        'fr': 'Windows (hors ligne)',
        'pt': 'Windows (sem internet)',
    },
    'voice.female': {
        'sk': 'žena',
        'en': 'female',
        'ja': '女性',
        'zh': '女声',
        'ru': 'женский',
        'es': 'femenina',
        'de': 'weiblich',
        'fr': 'féminine',
        'pt': 'feminina',
    },
    'voice.male': {
        'sk': 'muž',
        'en': 'male',
        'ja': '男性',
        'zh': '男声',
        'ru': 'мужской',
        'es': 'masculina',
        'de': 'männlich',
        'fr': 'masculine',
        'pt': 'masculina',
    },
    'voice.most_natural': {
        'sk': 'najprirodzenejší',
        'en': 'most natural',
        'ja': '最も自然',
        'zh': '最自然',
        'ru': 'самый естественный',
        'es': 'la más natural',
        'de': 'am natürlichsten',
        'fr': 'la plus naturelle',
        'pt': 'mais natural',
    },
    'voice.fallback_name': {
        'sk': 'Hlas {n}',
        'en': 'Voice {n}',
        'ja': '音声 {n}',
        'zh': '语音 {n}',
        'ru': 'Голос {n}',
        'es': 'Voz {n}',
        'de': 'Stimme {n}',
        'fr': 'Voix {n}',
        'pt': 'Voz {n}',
    },
    'voice.none': {
        'sk': '(žiadne hlasy)',
        'en': '(no voices)',
        'ja': '（音声なし）',
        'zh': '（无可用语音）',
        'ru': '(нет голосов)',
        'es': '(sin voces)',
        'de': '(keine Stimmen)',
        'fr': '(aucune voix)',
        'pt': '(sem vozes)',
    },
    'voice.loading': {
        'sk': '(načítavam...)',
        'en': '(loading...)',
        'ja': '（読み込み中...）',
        'zh': '（加载中…）',
        'ru': '(загрузка...)',
        'es': '(cargando...)',
        'de': '(wird geladen ...)',
        'fr': '(chargement...)',
        'pt': '(carregando...)',
    },
    'internal.empty_output': {
        'sk': 'prázdny výstup',
        'en': 'empty output',
        'ja': '空の出力',
        'zh': '输出为空',
        'ru': 'пустой вывод',
        'es': 'salida vacía',
        'de': 'leere Ausgabe',
        'fr': 'sortie vide',
        'pt': 'saída vazia',
    },
    'edge.ready': {
        'sk': '✓ hlas pripravený',
        'en': '✓ voice ready',
        'ja': '✓ 音声の準備完了',
        'zh': '✓ 语音已准备好',
        'ru': '✓ голос готов',
        'es': '✓ voz lista',
        'de': '✓ Stimme bereit',
        'fr': '✓ voix prête',
        'pt': '✓ voz pronta',
    },
    'edge.generating': {
        'sk': '⟳ pripravujem hlas…',
        'en': '⟳ preparing the voice…',
        'ja': '⟳ 音声を準備中…',
        'zh': '⟳ 正在准备语音…',
        'ru': '⟳ готовлю голос…',
        'es': '⟳ preparando la voz…',
        'de': '⟳ bereite die Stimme vor…',
        'fr': '⟳ je prépare la voix…',
        'pt': '⟳ preparando a voz…',
    },
    'edge.partial': {
        'sk': '! hlas má len {ok}/{total} pripomienok — skontroluj internet',
        'en': '! only {ok}/{total} cues have their voice — check your internet connection',
        'ja': '! 音声があるのは {ok}/{total} 件の合図だけ — インターネットを確認して',
        'zh': '! 只有 {ok}/{total} 条提示有语音——请检查网络',
        'ru': '! голос есть только у {ok}/{total} подсказок — проверь интернет',
        'es': '! solo {ok}/{total} avisos tienen voz — revisa tu conexión a internet',
        'de': '! nur {ok}/{total} Hinweise haben eine Stimme — prüf deine Internetverbindung',
        'fr': '! seulement {ok}/{total} rappels ont leur voix — vérifie ta connexion internet',
        'pt': '! só {ok}/{total} avisos têm voz — confira a sua internet',
    },
    'log.ready': {
        'sk': 'Som pripravená. Spustíš ma tlačidlom ▶ na páse hore.',
        'en': 'I’m ready. Start me with ▶ on the bar at the top.',
        'ja': '準備ができました。上のバーの ▶ で開始してください。',
        'zh': '我准备好了。点击顶部横条上的 ▶ 就能启动我。',
        'ru': 'Я готова. Запусти меня кнопкой ▶ на полосе вверху.',
        'es': 'Estoy lista. Iníciame con el botón ▶ de la barra de arriba.',
        'de': 'Ich bin bereit. Starte mich mit ▶ in der Leiste oben.',
        'fr': 'Je suis prête. Lance-moi avec ▶ dans la barre en haut.',
        'pt': 'Estou pronta. Você me inicia com ▶ na barra lá em cima.',
    },
    'log.edge_tts_missing': {
        'sk': 'Prirodzený hlas tu nie je k dispozícii — hovorím hlasom z Windows.',
        'en': 'The natural voice isn’t available here — speaking with the Windows voice.',
        'ja': 'ここでは自然な音声が使えません — Windows の音声で話します。',
        'zh': '这里无法使用自然语音——改用 Windows 语音。',
        'ru': 'Естественный голос здесь недоступен — говорю голосом Windows.',
        'es': 'La voz natural no está disponible aquí: hablo con la voz de Windows.',
        'de': 'Die natürliche Stimme ist hier nicht verfügbar — ich spreche mit der Windows-Stimme.',
        'fr': 'La voix naturelle n’est pas disponible ici — je parle avec la voix Windows.',
        'pt': 'A voz natural não está disponível aqui — falo com a voz do Windows.',
    },
    'log.theme_switched': {
        'sk': 'Vizuálny aj zvukový režim prepnutý na: {theme}',
        'en': 'Visual and sound mode switched to: {theme}',
        'ja': '見た目とサウンドのモードを切り替えました: {theme}',
        'zh': '视觉与声音主题已切换为：{theme}',
        'ru': 'Визуальный и звуковой режим переключён на: {theme}',
        'es': 'Modo visual y de sonido cambiado a: {theme}',
        'de': 'Visueller und akustischer Modus gewechselt zu: {theme}',
        'fr': 'Mode visuel et sonore changé pour : {theme}',
        'pt': 'Modo visual e sonoro alterado para: {theme}',
    },
    'log.lang_switched': {
        'sk': 'Jazyk rozhrania prepnutý na: {lang}',
        'en': 'Interface language switched to: {lang}',
        'ja': 'インターフェースの言語を切り替えました: {lang}',
        'zh': '界面语言已切换为：{lang}',
        'ru': 'Язык интерфейса переключён на: {lang}',
        'es': 'Idioma de la interfaz cambiado a: {lang}',
        'de': 'Oberflächensprache gewechselt zu: {lang}',
        'fr': "Langue de l'interface changée pour : {lang}",
        'pt': 'Idioma da interface alterado para: {lang}',
    },
    'lang.sk': {
        'sk': 'Slovenčina',
        'en': 'Slovak',
        'ja': 'スロバキア語',
        'zh': '斯洛伐克语',
        'ru': 'Словацкий',
        'es': 'Eslovaco',
        'de': 'Slowakisch',
        'fr': 'Slovaque',
        'pt': 'Eslovaco',
    },
    'lang.en': {
        'sk': 'Angličtina',
        'en': 'English',
        'ja': '英語',
        'zh': '英语',
        'ru': 'Английский',
        'es': 'Inglés',
        'de': 'Englisch',
        'fr': 'Anglais',
        'pt': 'Inglês',
    },
    'lang.ja': {
        'sk': 'Japončina',
        'en': 'Japanese',
        'ja': '日本語',
        'zh': '日语',
        'ru': 'Японский',
        'es': 'Japonés',
        'de': 'Japanisch',
        'fr': 'Japonais',
        'pt': 'Japonês',
    },
    'log.slot_removed': {
        'sk': 'Pripomienka odstránená ({label}).',
        'en': 'Cue removed ({label}).',
        'ja': '合図を削除しました（{label}）。',
        'zh': '提示已删除（{label}）。',
        'ru': 'Подсказка удалена ({label}).',
        'es': 'Aviso eliminado ({label}).',
        'de': 'Hinweis entfernt ({label}).',
        'fr': 'Rappel supprimé ({label}).',
        'pt': 'Aviso removido ({label}).',
    },
    'log.slot_only_one': {
        'sk': 'Musí zostať aspoň jedna pripomienka.',
        'en': 'At least one cue must remain.',
        'ja': '少なくとも1つの合図が必要です。',
        'zh': '至少需要保留一条提示。',
        'ru': 'Должна остаться хотя бы одна подсказка.',
        'es': 'Debe quedar al menos un aviso.',
        'de': 'Mindestens ein Hinweis muss übrig bleiben.',
        'fr': 'Il doit rester au moins un rappel.',
        'pt': 'Deve restar pelo menos um aviso.',
    },
    'log.slot_sfx_set': {
        'sk': 'Pripomienka {n}: zvuk = {name}',
        'en': 'Cue {n}: sound = {name}',
        'ja': '合図 {n}: 効果音 = {name}',
        'zh': '提示 {n}：音效 = {name}',
        'ru': 'Подсказка {n}: звук = {name}',
        'es': 'Aviso {n}: sonido = {name}',
        'de': 'Hinweis {n}: Ton = {name}',
        'fr': 'Rappel {n} : son = {name}',
        'pt': 'Aviso {n}: som = {name}',
    },
    'log.slot_recorded': {
        'sk': 'Pripomienka {n}: nahrané do {name}',
        'en': 'Cue {n}: recorded to {name}',
        'ja': '合図 {n}: {name} に録音しました',
        'zh': '提示 {n}：已录制为 {name}',
        'ru': 'Подсказка {n}: записано в {name}',
        'es': 'Aviso {n}: grabado en {name}',
        'de': 'Hinweis {n}: aufgenommen als {name}',
        'fr': 'Rappel {n} : enregistré sous {name}',
        'pt': 'Aviso {n}: gravado em {name}',
    },
    'log.slot_sfx_missing': {
        'sk': 'Pripomienka {n}: zvukový súbor chýba ({name}).',
        'en': 'Cue {n}: sound file is missing ({name}).',
        'ja': '合図 {n}: 効果音のファイルが見つかりません（{name}）。',
        'zh': '提示 {n}：音效文件缺失（{name}）。',
        'ru': 'Подсказка {n}: нет звукового файла ({name}).',
        'es': 'Aviso {n}: falta el archivo de sonido ({name}).',
        'de': 'Hinweis {n}: Tondatei fehlt ({name}).',
        'fr': 'Rappel {n} : fichier son manquant ({name}).',
        'pt': 'Aviso {n}: arquivo de som ausente ({name}).',
    },
    'log.slot_sfx_missing_fallback': {
        'sk': 'Pripomienka {n}: zvukový súbor chýba, hovorím text',
        'en': 'Cue {n}: sound file is missing, speaking the text instead',
        'ja': '合図 {n}: 効果音のファイルが見つからないため、代わりに文面を読み上げます',
        'zh': '提示 {n}：音效文件缺失，改为朗读文字',
        'ru': 'Подсказка {n}: нет звукового файла, вместо него озвучиваю текст',
        'es': 'Aviso {n}: falta el archivo de sonido, digo el texto en su lugar',
        'de': 'Hinweis {n}: Tondatei fehlt, ich spreche stattdessen den Text',
        'fr': 'Rappel {n} : fichier son manquant, je lis le texte à la place',
        'pt': 'Aviso {n}: arquivo de som ausente, falo o texto no lugar',
    },
    'log.slot_sfx_missing_plain': {
        'sk': 'Pripomienka {n}: zvukový súbor chýba.',
        'en': 'Cue {n}: sound file is missing.',
        'ja': '合図 {n}: 効果音のファイルが見つかりません。',
        'zh': '提示 {n}：音效文件缺失。',
        'ru': 'Подсказка {n}: нет звукового файла.',
        'es': 'Aviso {n}: falta el archivo de sonido.',
        'de': 'Hinweis {n}: Tondatei fehlt.',
        'fr': 'Rappel {n} : fichier son manquant.',
        'pt': 'Aviso {n}: arquivo de som ausente.',
    },
    'log.edge_loaded': {
        'sk': 'edge-tts načítané. Prepínam na prirodzené hlasy.',
        'en': 'edge-tts loaded. Switching to natural voices.',
        'ja': 'edge-tts を読み込みました。自然な音声に切り替えます。',
        'zh': 'edge-tts 已加载。切换为自然语音。',
        'ru': 'edge-tts загружен. Переключение на естественные голоса.',
        'es': 'edge-tts cargado. Cambiando a voces naturales.',
        'de': 'edge-tts geladen. Wechsle zu natürlichen Stimmen.',
        'fr': 'edge-tts chargé. Passage aux voix naturelles.',
        'pt': 'edge-tts carregado. Mudando para vozes naturais.',
    },
    'log.edge_still_missing': {
        'sk': 'edge-tts sa stále nedá načítať ({err})',
        'en': "edge-tts still can't be loaded ({err})",
        'ja': 'edge-tts をまだ読み込めません（{err}）',
        'zh': 'edge-tts 仍无法加载（{err}）',
        'ru': 'edge-tts всё ещё не удаётся загрузить ({err})',
        'es': 'edge-tts sigue sin poder cargarse ({err})',
        'de': 'edge-tts kann immer noch nicht geladen werden ({err})',
        'fr': 'edge-tts ne parvient toujours pas à se charger ({err})',
        'pt': 'o edge-tts ainda não consegue carregar ({err})',
    },
    'log.engine_switched': {
        'sk': 'Motor TTS: {engine}',
        'en': 'TTS engine: {engine}',
        'ja': 'TTSエンジン: {engine}',
        'zh': '语音引擎：{engine}',
        'ru': 'Движок TTS: {engine}',
        'es': 'Motor TTS: {engine}',
        'de': 'TTS-Engine: {engine}',
        'fr': 'Moteur TTS : {engine}',
        'pt': 'Motor de TTS: {engine}',
    },
    'log.edge_cache_ready': {
        'sk': 'Prirodzený hlas je pripravený pre {n} pripomienok — teraz znie aj bez internetu.',
        'en': 'Natural voice ready for {n} cues — they now play without internet too.',
        'ja': '{n} 件の合図の自然な音声を準備しました — インターネットなしでも再生できます。',
        'zh': '已为 {n} 条提示准备好自然语音——现在不联网也能播放。',
        'ru': 'Естественный голос готов для {n} подсказок — теперь они звучат и без интернета.',
        'es': 'Voz natural lista para {n} avisos: ya suenan también sin internet.',
        'de': 'Natürliche Stimme für {n} Hinweise bereit — sie klingen jetzt auch ohne Internet.',
        'fr': 'Voix naturelle prête pour {n} rappels — ils fonctionnent désormais aussi sans internet.',
        'pt': 'Voz natural pronta para {n} avisos — agora tocam também sem internet.',
    },
    'log.edge_not_cached': {
        'sk': 'Táto pripomienka ešte nemá pripravený prirodzený hlas — tentoraz hovorím hlasom z Windows a hlas pripravím hneď potom.',
        'en': 'This cue’s natural voice isn’t ready yet — speaking with the Windows voice this time, and I’ll prepare it right after.',
        'ja': 'この合図の自然な音声はまだ準備できていません — 今回は Windows の音声で話し、そのあとすぐ準備します。',
        'zh': '这条提示的自然语音还没准备好——这次我用 Windows 语音说，之后马上准备。',
        'ru': 'Естественный голос для этой подсказки ещё не готов — в этот раз говорю голосом Windows, а сразу после подготовлю его.',
        'es': 'La voz natural de este aviso aún no está lista: esta vez hablo con la voz de Windows y la preparo justo después.',
        'de': 'Die natürliche Stimme für diesen Hinweis ist noch nicht fertig — diesmal spreche ich mit der Windows-Stimme und bereite sie gleich danach vor.',
        'fr': 'La voix naturelle de ce rappel n’est pas encore prête — cette fois, je parle avec la voix Windows et je la prépare juste après.',
        'pt': 'A voz natural deste aviso ainda não está pronta — desta vez falo com a voz do Windows e preparo logo depois.',
    },
    'log.listening_on': {
        'sk': 'Sledovanie beží.',
        'en': 'Watching is on.',
        'ja': '見守りを始めました。',
        'zh': '已开始关注。',
        'ru': 'Наблюдение запущено.',
        'es': 'Observación en marcha.',
        'de': 'Beobachtung läuft.',
        'fr': 'Observation en cours.',
        'pt': 'Observação em andamento.',
    },
    'log.listening_off': {
        'sk': 'Sledovanie zastavené.',
        'en': 'Watching stopped.',
        'ja': '見守りを止めました。',
        'zh': '已停止关注。',
        'ru': 'Наблюдение остановлено.',
        'es': 'Observación detenida.',
        'de': 'Beobachtung gestoppt.',
        'fr': 'Observation arrêtée.',
        'pt': 'Observação parada.',
    },
    'log.settings_save_error': {
        'sk': 'Nastavenia sa nepodarilo uložiť: {err}',
        'en': "Couldn't save settings: {err}",
        'ja': '設定を保存できませんでした: {err}',
        'zh': '无法保存设置：{err}',
        'ru': 'Не удалось сохранить настройки: {err}',
        'es': 'No se pudo guardar la configuración: {err}',
        'de': 'Einstellungen konnten nicht gespeichert werden: {err}',
        'fr': "Impossible d'enregistrer les réglages : {err}",
        'pt': 'Não foi possível salvar as configurações: {err}',
    },
    'log.audio_error': {
        'sk': 'CHYBA zvuku: {err}',
        'en': 'AUDIO ERROR: {err}',
        'ja': '音声エラー: {err}',
        'zh': '音频错误：{err}',
        'ru': 'ОШИБКА АУДИО: {err}',
        'es': 'ERROR DE AUDIO: {err}',
        'de': 'AUDIO-FEHLER: {err}',
        'fr': 'ERREUR AUDIO : {err}',
        'pt': 'ERRO DE ÁUDIO: {err}',
    },
    'log.playback_error': {
        'sk': 'CHYBA prehrávania: {err}',
        'en': 'PLAYBACK ERROR: {err}',
        'ja': '再生エラー: {err}',
        'zh': '播放错误：{err}',
        'ru': 'ОШИБКА ВОСПРОИЗВЕДЕНИЯ: {err}',
        'es': 'ERROR DE REPRODUCCIÓN: {err}',
        'de': 'WIEDERGABEFEHLER: {err}',
        'fr': 'ERREUR DE LECTURE : {err}',
        'pt': 'ERRO DE REPRODUÇÃO: {err}',
    },
    'log.sfx_playback_error': {
        'sk': 'CHYBA prehrávania SFX: {err}',
        'en': 'SFX PLAYBACK ERROR: {err}',
        'ja': 'SFX再生エラー: {err}',
        'zh': '音效播放错误：{err}',
        'ru': 'ОШИБКА ВОСПРОИЗВЕДЕНИЯ SFX: {err}',
        'es': 'ERROR DE REPRODUCCIÓN SFX: {err}',
        'de': 'SFX-WIEDERGABEFEHLER: {err}',
        'fr': 'ERREUR DE LECTURE SFX : {err}',
        'pt': 'ERRO DE REPRODUÇÃO DE SFX: {err}',
    },
    'log.tts_error': {
        'sk': 'CHYBA TTS: {err}',
        'en': 'TTS ERROR: {err}',
        'ja': 'TTSエラー: {err}',
        'zh': '语音合成错误：{err}',
        'ru': 'ОШИБКА TTS: {err}',
        'es': 'ERROR DE TTS: {err}',
        'de': 'TTS-FEHLER: {err}',
        'fr': 'ERREUR TTS : {err}',
        'pt': 'ERRO DE TTS: {err}',
    },
    'log.edge_gen_failed': {
        'sk': 'Prirodzený hlas pre „{text}“ sa nepodarilo pripraviť ({err}).',
        'en': 'Couldn’t prepare the natural voice for “{text}” ({err}).',
        'ja': '「{text}」の自然な音声を準備できませんでした（{err}）。',
        'zh': '无法为“{text}”准备自然语音（{err}）。',
        'ru': 'Не удалось подготовить естественный голос для «{text}» ({err}).',
        'es': 'No se pudo preparar la voz natural para «{text}» ({err}).',
        'de': 'Die natürliche Stimme für „{text}“ ließ sich nicht vorbereiten ({err}).',
        'fr': 'Impossible de préparer la voix naturelle pour « {text} » ({err}).',
        'pt': 'Não foi possível preparar a voz natural para “{text}” ({err}).',
    },
    'log.sapi_ready': {
        'sk': 'Hlas z Windows je pripravený.',
        'en': 'The Windows voice is ready.',
        'ja': 'Windows の音声の準備ができました。',
        'zh': 'Windows 语音已准备好。',
        'ru': 'Голос Windows готов.',
        'es': 'La voz de Windows está lista.',
        'de': 'Die Windows-Stimme ist bereit.',
        'fr': 'La voix Windows est prête.',
        'pt': 'A voz do Windows está pronta.',
    },
    'log.sapi_unavailable': {
        'sk': 'Hlas z Windows sa nepodarilo pripraviť ({err}) — skúšam náhradný spôsob.',
        'en': 'Couldn’t prepare the Windows voice ({err}) — trying a fallback.',
        'ja': 'Windows の音声を準備できませんでした（{err}）— 代わりの方法を試します。',
        'zh': '无法准备 Windows 语音（{err}）——正在尝试备用方式。',
        'ru': 'Не удалось подготовить голос Windows ({err}) — пробую запасной способ.',
        'es': 'No se pudo preparar la voz de Windows ({err}): pruebo una alternativa.',
        'de': 'Die Windows-Stimme ließ sich nicht vorbereiten ({err}) — ich versuche einen Ausweg.',
        'fr': 'Impossible de préparer la voix Windows ({err}) — j’essaie une solution de secours.',
        'pt': 'Não foi possível preparar a voz do Windows ({err}) — tentando outra forma.',
    },
    'tray.show': {
        'sk': 'Zobraziť',
        'en': 'Show',
        'ja': '表示',
        'zh': '显示',
        'ru': 'Показать',
        'es': 'Mostrar',
        'de': 'Anzeigen',
        'fr': 'Afficher',
        'pt': 'Mostrar',
    },
    'tray.quit': {
        'sk': 'Ukončiť',
        'en': 'Quit',
        'ja': '終了',
        'zh': '退出',
        'ru': 'Выход',
        'es': 'Salir',
        'de': 'Beenden',
        'fr': 'Quitter',
        'pt': 'Sair',
    },
    # 0.3: a second launch of the app (main.py, single instance). Shown only
    # when the running copy did not get the "show window" signal - otherwise
    # the window shows itself.
    'tray.already_running': {
        'sk': 'Zanshin už beží — nájdeš ho v lište pri hodinách (ak ikonu nevidíš, klikni na šípku ^).',
        'en': 'Zanshin is already running — you’ll find it in the tray by the clock (if you don’t see the icon, click the ^ arrow).',
        'ja': 'Zanshin はすでに起動しています — 時計の横のトレイにあります（アイコンが見えない場合は、矢印 ^ をクリックしてください）。',
        'zh': 'Zanshin 已在运行——可以在时钟旁的托盘中找到它（如果看不到图标，请点击箭头 ^）。',
        'ru': 'Zanshin уже запущен — он в трее рядом с часами (если не видишь значок, нажми на стрелку ^).',
        'es': 'Zanshin ya está en ejecución — lo encontrarás en la bandeja junto al reloj (si no ves el icono, haz clic en la flecha ^).',
        'de': 'Zanshin läuft bereits — du findest es im Infobereich neben der Uhr (wenn du das Symbol nicht siehst, klicke auf den Pfeil ^).',
        'fr': 'Zanshin est déjà lancé — tu le trouveras dans la zone de notification, près de l’horloge (si tu ne vois pas l’icône, clique sur la flèche ^).',
        'pt': 'O Zanshin já está em execução — você o encontra na bandeja, perto do relógio (se não vir o ícone, clique na seta ^).',
    },
    'msgbox.edge_still_missing': {
        'sk': 'edge-tts sa stále nepodarilo načítať.\n\nChyba: {err}\n\nSpusti v príkazovom riadku:\n    pip install edge-tts\n\nAk máš viac inštalácií Pythonu, použi tú istú, ktorou spúšťaš túto appku:\n    python -m pip install edge-tts',
        'en': "edge-tts still couldn't be loaded.\n\nError: {err}\n\nRun in a terminal:\n    pip install edge-tts\n\nIf you have multiple Python installs, use the same one that runs this app:\n    python -m pip install edge-tts",
        'ja': 'edge-tts をまだ読み込めませんでした。\n\nエラー: {err}\n\nターミナルで実行してください:\n    pip install edge-tts\n\n複数のPythonがインストールされている場合は、このアプリを実行しているものと同じPythonを使ってください:\n    python -m pip install edge-tts',
        'zh': 'edge-tts 仍无法加载。\n\n错误：{err}\n\n请在终端运行：\n    pip install edge-tts\n\n如果你安装了多个 Python 版本，请使用运行本应用的那一个：\n    python -m pip install edge-tts',
        'ru': 'edge-tts всё ещё не удалось загрузить.\n\nОшибка: {err}\n\nВыполни в терминале:\n    pip install edge-tts\n\nЕсли у тебя установлено несколько версий Python, используй ту же, что запускает это приложение:\n    python -m pip install edge-tts',
        'es': 'edge-tts sigue sin poder cargarse.\n\nError: {err}\n\nEjecuta en una terminal:\n    pip install edge-tts\n\nSi tienes varias instalaciones de Python, usa la misma que ejecuta esta app:\n    python -m pip install edge-tts',
        'de': 'edge-tts konnte immer noch nicht geladen werden.\n\nFehler: {err}\n\nFühre im Terminal aus:\n    pip install edge-tts\n\nWenn du mehrere Python-Installationen hast, verwende dieselbe, die diese App ausführt:\n    python -m pip install edge-tts',
        'fr': 'edge-tts ne parvient toujours pas à se charger.\n\nErreur : {err}\n\nExécute dans un terminal :\n    pip install edge-tts\n\nSi tu as plusieurs installations de Python, utilise celle qui exécute cette appli :\n    python -m pip install edge-tts',
        'pt': 'o edge-tts ainda não conseguiu carregar.\n\nErro: {err}\n\nExecute no terminal:\n    pip install edge-tts\n\nSe você tem várias instalações do Python, use a mesma que executa este app:\n    python -m pip install edge-tts',
    },
    'msgbox.edge_missing_body': {
        'sk': 'Knižnica edge-tts nie je nainštalovaná.\n\nNainštaluj ju príkazom:\n    pip install edge-tts',
        'en': "The edge-tts library isn't installed.\n\nInstall it with:\n    pip install edge-tts",
        'ja': 'edge-tts ライブラリがインストールされていません。\n\n次のコマンドでインストールしてください:\n    pip install edge-tts',
        'zh': '未安装 edge-tts 库。\n\n安装方法：\n    pip install edge-tts',
        'ru': 'Библиотека edge-tts не установлена.\n\nУстанови её командой:\n    pip install edge-tts',
        'es': 'La librería edge-tts no está instalada.\n\nInstálala con:\n    pip install edge-tts',
        'de': 'Die edge-tts-Bibliothek ist nicht installiert.\n\nInstalliere sie mit:\n    pip install edge-tts',
        'fr': "La bibliothèque edge-tts n'est pas installée.\n\nInstalle-la avec :\n    pip install edge-tts",
        'pt': 'A biblioteca edge-tts não está instalada.\n\nInstale com:\n    pip install edge-tts',
    },
    # Without 📖 (0.3, batch 4): the emoji was the only coloured symbol in a
    # heading in the Guide window - audit: no emoji in labels.
    'guide.panel_title': {
        'sk': 'Sprievodca / Čo je za tým',
        'en': 'Guide / What’s behind it',
        'ja': 'ガイド / その背景',
        'zh': '指南 / 背后的道理',
        'ru': 'Справочник / Что за этим стоит',
        'es': 'Guía / Qué hay detrás',
        'de': 'Leitfaden / Was dahintersteckt',
        'fr': 'Guide / Ce qu’il y a derrière',
        'pt': 'Guia / O que há por trás',
    },
    'guide.panel_subtitle': {
        'sk': 'Čo sa ti v tele deje pri každej pripomienke a čo s tým spraviť, keď sa appka ozve.',
        'en': 'What happens in your body at each cue, and what to do about it when the app speaks.',
        'ja': '各リマインドで体に何が起きているか、そしてアプリが話しかけたときに何をすればよいか。',
        'zh': '每次提示时你身体里发生了什么，以及应用出声时该怎么做。',
        'ru': 'Что происходит в теле при каждой подсказке и что с этим делать, когда приложение заговорит.',
        'es': 'Qué ocurre en tu cuerpo en cada aviso y qué hacer cuando la app habla.',
        'de': 'Was in deinem Körper bei jedem Hinweis passiert und was du tust, wenn die App sich meldet.',
        'fr': "Ce qui se passe dans ton corps à chaque rappel, et quoi en faire quand l'app parle.",
        'pt': 'O que acontece no teu corpo em cada aviso e o que fazer quando o app fala.',
    },
    'guide.window_title': {
        'sk': 'Sprievodca · Čo je za tým',
        'en': 'Guide · What’s behind it',
        'ja': 'ガイド · その背景',
        'zh': '指南 · 背后的道理',
        'ru': 'Справочник · Что за этим стоит',
        'es': 'Guía · Qué hay detrás',
        'de': 'Leitfaden · Was dahintersteckt',
        'fr': 'Guide · Ce qu’il y a derrière',
        'pt': 'Guia · O que há por trás',
    },
    'guide.block.physiology': {
        'sk': 'Fyziológia',
        'en': 'Physiology',
        'ja': '生理学',
        'zh': '生理学',
        'ru': 'Физиология',
        'es': 'Fisiología',
        'de': 'Physiologie',
        'fr': 'Physiologie',
        'pt': 'Fisiologia',
    },
    'guide.block.instruction': {
        'sk': 'Čo môžeš urobiť',
        'en': 'What you can do',
        'ja': 'あなたにできること',
        'zh': '你可以做什么',
        'ru': 'Что ты можешь сделать',
        'es': 'Qué puedes hacer',
        'de': 'Was du tun kannst',
        'fr': 'Ce que tu peux faire',
        'pt': 'O que você pode fazer',
    },
    'guide.block.steps_title': {
        'sk': 'Postup',
        'en': 'Steps',
        'ja': '手順',
        'zh': '步骤',
        'ru': 'Шаги',
        'es': 'Pasos',
        'de': 'Schritte',
        'fr': 'Étapes',
        'pt': 'Passos',
    },
    'guide.block.why_title': {
        'sk': 'Prečo to môže pomôcť',
        'en': 'Why it may help',
        'ja': '役立つかもしれない理由',
        'zh': '为什么可能有帮助',
        'ru': 'Почему это может помочь',
        'es': 'Por qué puede ayudar',
        'de': 'Warum es helfen kann',
        'fr': 'Pourquoi ça peut aider',
        'pt': 'Por que pode ajudar',
    },
    'guide.grounding.title': {
        'sk': 'Ťažisko',
        'en': 'Grounding',
        'ja': '重心',
        'zh': '重心',
        'ru': 'Опора',
        'es': 'Centro',
        'de': 'Erdung',
        'fr': 'Ancrage',
        'pt': 'Centro',
    },
    'guide.grounding.trigger': {
        'sk': 'Keď sa telo zlomí dopredu k monitoru',
        'en': 'When your body folds forward toward the monitor',
        'ja': '体がモニターへ前に折れていくとき',
        'zh': '当身体向显示器前倾时',
        'ru': 'Когда тело складывается вперёд к монитору',
        'es': 'Cuando el cuerpo se dobla hacia el monitor',
        'de': 'Wenn der Körper sich zum Monitor nach vorn faltet',
        'fr': "Quand le corps se plie vers l'écran",
        'pt': 'Quando o corpo se dobra para a frente, para o monitor',
    },
    # 0.2: a description of what happens to your posture during the
    # exercise - not a claim about "activating the stabilisation system"
    # without a source.
    'guide.grounding.physiology': {
        'sk': 'Chrbtica sa vzpriami a váha sa presunie na sedacie kosti a chodidlá.',
        'en': 'The spine straightens and your weight settles onto your sit bones and feet.',
        'ja': '背骨がまっすぐになり、体重が坐骨と足の裏に乗ります。',
        'zh': '脊柱挺直，身体的重量落到坐骨和双脚上。',
        'ru': 'Позвоночник выпрямляется, и вес переходит на седалищные кости и стопы.',
        'es': 'La columna se endereza y el peso se asienta sobre los isquiones y los pies.',
        'de': 'Die Wirbelsäule richtet sich auf, und das Gewicht verlagert sich auf die Sitzknochen und die Füße.',
        'fr': 'La colonne se redresse et le poids se pose sur les ischions et les pieds.',
        'pt': 'A coluna se endireita e o peso se assenta sobre os ísquios e os pés.',
    },
    # Honesty (KNOWN_ISSUES.md point 4): the texts under "Why it may help"
    # no longer claim mechanisms as fact. A study is cited only where it is
    # in PHILOSOPHY_SOURCES (guide_content.py) and its label really covers
    # it; otherwise the text says it is practice / tradition and invites the
    # player to try it on themselves („skús, či…“ - try whether...) - we
    # have no data about players, so we do not say „mnohým pomôže“ (it will
    # help many). The other languages are from the 0.2 language phase
    # (before that temporarily = en). Guarded by tests/test_guide_honesty.py
    # (all languages).
    'guide.grounding.science': {
        'sk': 'Keď hra pritlačí, ľahko sa nevedomky zosunieš k monitoru — hlava vpredu, ramená hore („turtle neck“). Neskôr to môžeš cítiť v krku a ramenách. Keď si všimneš sedacie kosti a chodidlá na zemi, máš sa o čo oprieť — skús, či ti to pomôže povoliť. Toto je z praxe, nie z laboratória.',
        'en': 'When a game gets tense, it’s easy to drift toward the monitor without noticing — head forward, shoulders up (the “turtle neck”). You may feel it later in your neck and shoulders. Noticing your sit bones and your feet on the floor gives you something to lean on — see whether it helps you let go. This comes from practice, not from a lab.',
        'ja': 'ゲームが緊迫すると、気づかないうちにモニターへ引き寄せられがちです — 頭が前に出て、肩が上がる（いわゆる「亀首」）。あとになって首や肩に感じることもあります。坐骨と、床についた足の裏に気づくと、よりどころができます — それで力を抜きやすくなるか試してみてください。これは実践から来たもので、実験室から来たものではありません。',
        'zh': '游戏一紧张，人很容易不知不觉地向显示器凑过去——头往前伸，肩膀耸起（“乌龟颈”）。之后你可能会在脖子和肩膀上感觉到。留意坐骨和踩在地上的双脚，你就有了可以依靠的支点——试试看这能不能帮你松下来。这来自实践，而不是实验室。',
        'ru': 'Когда игра давит, легко незаметно сползти к монитору — голова вперёд, плечи вверх («черепашья шея»). Позже это может отозваться в шее и плечах. Если заметить седалищные кости и стопы на полу, появляется на что опереться — попробуй, поможет ли тебе это отпустить напряжение. Это из практики, а не из лаборатории.',
        'es': 'Cuando el juego aprieta, es fácil irte hundiendo hacia el monitor sin darte cuenta — la cabeza adelantada, los hombros arriba (el «turtle neck», cuello de tortuga). Más tarde puedes notarlo en el cuello y los hombros. Cuando notas los isquiones y los pies en el suelo, tienes algo en lo que apoyarte — prueba si te ayuda a soltar. Esto viene de la práctica, no del laboratorio.',
        'de': 'Wenn das Spiel Druck macht, rutschst du leicht unbemerkt zum Monitor hin — Kopf nach vorn, Schultern hoch („Turtle Neck“). Später kannst du das in Nacken und Schultern spüren. Wenn du deine Sitzknochen und die Füße auf dem Boden bemerkst, hast du etwas, worauf du dich stützen kannst — probier, ob dir das hilft loszulassen. Das stammt aus der Praxis, nicht aus dem Labor.',
        'fr': 'Quand le jeu met la pression, tu glisses facilement vers l’écran sans t’en rendre compte — tête en avant, épaules remontées (le « turtle neck »). Plus tard, tu peux le sentir dans le cou et les épaules. Quand tu remarques tes ischions et tes pieds posés au sol, tu as quelque chose sur quoi t’appuyer — vois si ça t’aide à relâcher. Ceci vient de la pratique, pas d’un laboratoire.',
        'pt': 'Quando o jogo aperta, é fácil escorregar em direção ao monitor sem perceber — cabeça para a frente, ombros para cima (“turtle neck”). Depois você pode sentir isso no pescoço e nos ombros. Quando você percebe os ísquios e os pés no chão, tem onde se apoiar — veja se isso te ajuda a soltar. Isto vem da prática, não do laboratório.',
    },
    'guide.grounding.instruction': {
        'sk': 'Keď sa appka ozve, nezosýpaj sa dopredu — precíť, ako sa sedacie kosti zaboria do stoličky. Uvoľni spodnú časť brucha a nechaj ramená padnúť. Hlava hore, ťažisko dole.',
        'en': "When the app speaks up, don't fold forward - feel your sit bones sink into the chair. Release the lower belly and let your shoulders drop. Head up, center of gravity down.",
        'ja': 'アプリが声をかけたら、前に崩れないで – 坐骨が椅子に沈み込むのを感じてください。下腹をゆるめ、肩を落とします。頭は上に、重心は下に。',
        'zh': '应用出声时，别向前塌——感受坐骨沉进椅子里。放松小腹，让肩膀落下。头向上，重心向下。',
        'ru': 'Когда приложение подаст голос, не складывайся вперёд – почувствуй, как седалищные кости погружаются в стул. Расслабь низ живота и дай плечам опуститься. Голова вверх, центр тяжести вниз.',
        'es': 'Cuando la app te avise, no te derrumbes hacia delante – siente cómo los isquiones se hunden en la silla. Suelta la parte baja del abdomen y deja caer los hombros. La cabeza arriba, el centro de gravedad abajo.',
        'de': 'Wenn sich die App meldet, sack nicht nach vorn zusammen – spür, wie deine Sitzknochen in den Stuhl sinken. Lass den Unterbauch locker und die Schultern fallen. Kopf hoch, Schwerpunkt nach unten.',
        'fr': 'Quand l’app se manifeste, ne t’affaisse pas vers l’avant – sens tes ischions s’enfoncer dans la chaise. Relâche le bas du ventre et laisse tomber les épaules. Tête haute, centre de gravité en bas.',
        'pt': 'Quando o app avisar, não desabe para a frente – sinta os seus ísquios afundarem na cadeira. Solte a parte de baixo da barriga e deixe os ombros caírem. Cabeça erguida, centro de gravidade embaixo.',
    },
    'guide.grounding.sketch_caption': {
        'sk': 'hara / ťažisko',
        'en': 'hara / center of gravity',
        'ja': '丹田 / 重心',
        'zh': '丹田 / 重心',
        'ru': 'хара / центр тяжести',
        'es': 'hara / centro de gravedad',
        'de': 'Hara / Schwerpunkt',
        'fr': 'hara / centre de gravité',
        'pt': 'hara / centro de gravidade',
    },
    'guide.jaw.title': {
        'sk': 'Čeľusť',
        'en': 'Jaw',
        'ja': '顎',
        'zh': '下颌',
        'ru': 'Челюсть',
        'es': 'Mandíbula',
        'de': 'Kiefer',
        'fr': 'Mâchoire',
        'pt': 'Mandíbula',
    },
    'guide.jaw.trigger': {
        'sk': 'Keď zatneš čeľusť a nevieš o tom',
        'en': 'When your jaw clenches without you noticing',
        'ja': '気づかないうちに顎を食いしばっているとき',
        'zh': '当你不自觉地咬紧下颌时',
        'ru': 'Когда челюсть сжимается, а ты этого не замечаешь',
        'es': 'Cuando aprietas la mandíbula sin darte cuenta',
        'de': 'Wenn sich der Kiefer verkrampft, ohne dass du es merkst',
        'fr': 'Quand la mâchoire se serre sans que tu le remarques',
        'pt': 'Quando você trava a mandíbula sem perceber',
    },
    'guide.jaw.physiology': {
        'sk': 'Maseter (hlavný žuvací sval) a trojklanný nerv (nervus trigeminus).',
        'en': 'The masseter (main chewing muscle) and the trigeminal nerve.',
        'ja': '咬筋（主要な咀嚼筋）と三叉神経。',
        'zh': '咬肌（主要咀嚼肌）与三叉神经。',
        'ru': 'Жевательная мышца (masseter) и тройничный нерв.',
        'es': 'El masetero (músculo masticatorio principal) y el nervio trigémino.',
        'de': 'Der Masseter (Hauptkaumuskel) und der Trigeminusnerv.',
        'fr': 'Le masséter (muscle masticateur principal) et le nerf trijumeau.',
        'pt': 'O masseter (principal músculo mastigatório) e o nervo trigêmeo.',
    },
    'guide.jaw.science': {
        'sk': 'Súťažné hranie vie rozbehnúť skutočnú stresovú reakciu srdca a nervového systému (Ketelhut & Nigg 2024, v zdrojoch nižšie). Kde ju nosíš ty, je iná otázka — skús si všimnúť, či nie v zatnutej čeľusti; môžu sa k nej pridať aj krk a ramená. Či ti to kazí mierenie, zistíš len na sebe: na chvíľu zatni zuby, pohni myšou či gamepadom, potom povoľ a porovnaj.',
        'en': 'Competitive play can switch on a real stress response in your heart and nervous system (Ketelhut & Nigg 2024, in the sources below). Where you carry it is another question — notice whether it’s in a clenched jaw; your neck and shoulders may join in. Whether it hurts your aim, only you can tell: clench for a moment, move the mouse or gamepad, then let go and compare.',
        'ja': '競技的なプレイは、心臓と神経系に本物のストレス反応を引き起こすことがあります（Ketelhut & Nigg 2024、下の出典を参照）。それを体のどこに抱えるかは別の問題です — 顎を食いしばっていないか気づいてみてください。首や肩も加わるかもしれません。それがエイムを乱すかどうかは、自分で確かめるしかありません。少しのあいだ歯を食いしばってマウスやゲームパッドを動かし、それから力を抜いて比べてみてください。',
        'zh': '竞技游戏能够引发心脏和神经系统真实的应激反应（Ketelhut & Nigg 2024，见下方参考来源）。它积在你身上的哪里，是另一个问题——留意一下是不是在咬紧的下颌里；脖子和肩膀也可能跟着一起紧。这会不会影响你的瞄准，只有在自己身上才能试出来：咬紧牙关片刻，动一动鼠标或手柄，然后松开，比较一下。',
        'ru': 'Соревновательная игра может запустить настоящую стрессовую реакцию сердца и нервной системы (Ketelhut & Nigg 2024, в источниках ниже). Где её носишь ты — другой вопрос: попробуй заметить, не в сжатой ли челюсти; к ней могут присоединиться шея и плечи. Мешает ли это тебе целиться, узнаешь только на себе: на миг сожми зубы, подвигай мышью или геймпадом, потом расслабь и сравни.',
        'es': 'El juego competitivo puede poner en marcha una respuesta de estrés real en el corazón y el sistema nervioso (Ketelhut & Nigg 2024, en las fuentes de abajo). Dónde la cargas tú es otra cuestión — fíjate si no es en la mandíbula apretada; también pueden sumarse el cuello y los hombros. Si eso te estropea la puntería, solo lo sabrás probándolo en ti: aprieta los dientes un momento, mueve el ratón o el mando, luego suelta y compara.',
        'de': 'Kompetitives Spielen kann eine echte Stressreaktion von Herz und Nervensystem in Gang setzen (Ketelhut & Nigg 2024, in den Quellen unten). Wo du sie trägst, ist eine andere Frage — achte mal darauf, ob sie nicht im zusammengebissenen Kiefer sitzt; auch Nacken und Schultern können dazukommen. Ob sie dir das Zielen verdirbt, findest du nur an dir selbst heraus: Beiß kurz die Zähne zusammen, beweg Maus oder Gamepad, dann lass locker und vergleiche.',
        'fr': 'Le jeu compétitif peut déclencher une véritable réaction de stress du cœur et du système nerveux (Ketelhut & Nigg 2024, dans les sources ci-dessous). Où tu la portes, c’est une autre question — regarde si ce n’est pas dans une mâchoire serrée ; le cou et les épaules peuvent s’y ajouter. Si ça nuit à ta visée, tu ne le découvriras que sur toi-même : serre les dents un instant, bouge la souris ou la manette, puis relâche et compare.',
        'pt': 'O jogo competitivo pode desencadear uma resposta real de estresse no coração e no sistema nervoso (Ketelhut & Nigg 2024, nas fontes abaixo). Onde você a carrega é outra questão — observe se não está numa mandíbula travada; pescoço e ombros também podem entrar junto. Se isso atrapalha a sua mira, só dá para descobrir em você mesmo: trave os dentes por um momento, mexa o mouse ou o gamepad, depois solte e compare.',
    },
    'guide.jaw.instruction': {
        'sk': 'Počas animácie reloadu oddel zuby od seba na 2 milimetre a odlep jazyk od horného podnebia. Povoľ svaly okolo úst. Skús, či s čeľusťou povolí aj zápästie.',
        'en': 'During the reload animation, part your teeth by about 2 millimeters and lift your tongue off the roof of your mouth. Release the muscles around your mouth. See whether your wrist lets go along with your jaw.',
        'ja': 'リロードのアニメーション中に、上下の歯を2ミリほど離し、舌を上あごから離します。口のまわりの筋肉をゆるめます。顎と一緒に手首もゆるむか試してみてください。',
        'zh': '换弹动画期间，让上下牙分开 2 毫米，舌头离开上颚。放松嘴巴周围的肌肉。试试看下颌松开时，手腕是否也会跟着放松。',
        'ru': 'Во время анимации перезарядки разомкни зубы на 2 миллиметра и отлепи язык от нёба. Расслабь мышцы вокруг рта. Попробуй, расслабится ли вместе с челюстью и запястье.',
        'es': 'Durante la animación de recarga, separa los dientes unos 2 milímetros y despega la lengua del paladar. Suelta los músculos alrededor de la boca. Prueba si, con la mandíbula, se suelta también la muñeca.',
        'de': 'Nimm während der Nachladeanimation die Zähne 2 Millimeter auseinander und löse die Zunge vom oberen Gaumen. Lass die Muskeln um den Mund locker. Probier, ob mit dem Kiefer auch das Handgelenk loslässt.',
        'fr': 'Pendant l’animation de rechargement, écarte les dents de 2 millimètres et décolle la langue du palais. Relâche les muscles autour de la bouche. Vois si ton poignet se relâche aussi avec la mâchoire.',
        'pt': 'Durante a animação de recarga, afaste os dentes uns 2 milímetros e descole a língua do céu da boca. Solte os músculos em volta da boca. Veja se o punho também se solta junto com a mandíbula.',
    },
    'guide.jaw.sketch_caption': {
        'sk': 'uvoľnená čeľusť',
        'en': 'relaxed jaw',
        'ja': '脱力した顎',
        'zh': '放松的下颌',
        'ru': 'расслабленная челюсть',
        'es': 'mandíbula relajada',
        'de': 'entspannter Kiefer',
        'fr': 'mâchoire détendue',
        'pt': 'mandíbula relaxada',
    },
    'guide.periphery.title': {
        'sk': 'Ruka a pohľad',
        'en': 'Grip & gaze',
        'ja': '手と視線',
        'zh': '手与视线',
        'ru': 'Рука и взгляд',
        'es': 'Mano y mirada',
        'de': 'Hand und Blick',
        'fr': 'Main et regard',
        'pt': 'Mão e olhar',
    },
    'guide.periphery.trigger': {
        'sk': 'Keď sa zahryzneš pohľadom do zameriavača',
        'en': 'When your eyes lock onto the crosshair',
        'ja': '視線がクロスヘアに食い込んでいるとき',
        'zh': '当视线死死咬住准星时',
        'ru': 'Когда взгляд впивается в прицел',
        'es': 'Cuando la mirada se clava en la mira',
        'de': 'Wenn sich der Blick im Fadenkreuz festbeißt',
        'fr': 'Quand le regard se fige sur le réticule',
        'pt': 'Quando o olhar se crava na mira',
    },
    'guide.periphery.physiology': {
        'sk': 'Úzky, zabodnutý pohľad (centrálne videnie) vs. široký, mäkký pohľad (periférne videnie).',
        'en': 'A narrow, locked-on gaze (central vision) vs. a wide, soft one (peripheral vision).',
        'ja': '狭く、一点に突き刺さる視線（中心視）と、広くやわらかな視線（周辺視）。',
        'zh': '狭窄、死盯的目光（中央视野）vs. 宽阔、柔和的目光（周边视野）。',
        'ru': 'Узкий, впившийся взгляд (центральное зрение) против широкого, мягкого взгляда (периферийное зрение).',
        'es': 'Una mirada estrecha y clavada (visión central) frente a una mirada amplia y suave (visión periférica).',
        'de': 'Enger, starrer Blick (zentrales Sehen) vs. weiter, weicher Blick (peripheres Sehen).',
        'fr': 'Un regard étroit et figé (vision centrale) vs. un regard large et doux (vision périphérique).',
        'pt': 'Olhar estreito e cravado (visão central) vs. olhar amplo e suave (visão periférica).',
    },
    'guide.periphery.science': {
        'sk': 'Pod tlakom sa pozornosť vie zúžiť — oči sa zabodnú do zameriavača a okraje obrazovky akoby zmizli. Mäkký, široký pohľad je starý pokyn z bojových umení (v kende „enzan no metsuke“ — pohľad ako na vzdialenú horu). Skús, či tak skôr zachytíš pohyb na okraji a či ruka povolí. Je to tradícia, nie zmeraný mechanizmus.',
        'en': 'Under pressure, attention can narrow — your eyes lock onto the crosshair and the edges of the screen seem to fade. A soft, wide gaze is an old martial-arts cue (kendo’s “enzan no metsuke” — looking as if at a distant mountain). See whether you catch movement at the edges sooner that way, and whether your grip loosens. It’s a tradition, not a measured mechanism.',
        'ja': 'プレッシャーの下では、注意が狭まることがあります — 目がクロスヘアに釘づけになり、画面の端が消えたように感じます。やわらかく広い視線は、武道の古い教えです（剣道でいう「遠山の目付」— 遠くの山を見るような目）。そのほうが端の動きに早く気づけるか、手の力が抜けるか試してみてください。これは伝統であって、測定された仕組みではありません。',
        'zh': '在压力下，注意力可能会收窄——眼睛死死盯住准星，屏幕边缘仿佛消失了。柔和、宽阔的目光是武道里一条古老的要诀（剑道里的“enzan no metsuke”，即远山之目付——像望着远处的山那样看）。试试看这样能不能更早察觉边缘的动静，手是否也会松下来。这是传统，而不是经过测量的机制。',
        'ru': 'Под давлением внимание может сужаться — глаза впиваются в прицел, а края экрана будто исчезают. Мягкий, широкий взгляд — старое указание из боевых искусств (в кэндо «эндзан-но мэцукэ» — взгляд как на далёкую гору). Попробуй, замечаешь ли так раньше движение на краю и расслабляется ли рука. Это традиция, а не измеренный механизм.',
        'es': 'Bajo presión, la atención puede estrecharse — los ojos se clavan en la mira y los bordes de la pantalla parecen desaparecer. La mirada suave y amplia es una vieja indicación de las artes marciales (en kendo, «enzan no metsuke» — mirar como a una montaña lejana). Prueba si así captas antes el movimiento en los bordes y si la mano se afloja. Es una tradición, no un mecanismo medido.',
        'de': 'Unter Druck kann sich die Aufmerksamkeit verengen — die Augen bohren sich ins Fadenkreuz, und die Ränder des Bildschirms scheinen zu verschwinden. Ein weicher, weiter Blick ist eine alte Anweisung aus den Kampfkünsten (im Kendo „enzan no metsuke“ — der Blick wie auf einen fernen Berg). Probier, ob du so Bewegung am Rand eher wahrnimmst und ob die Hand loslässt. Das ist Tradition, kein gemessener Mechanismus.',
        'fr': 'Sous pression, l’attention peut se rétrécir — les yeux se figent sur le réticule et les bords de l’écran semblent disparaître. Le regard doux et large est une vieille consigne des arts martiaux (en kendo, « enzan no metsuke » — regarder comme on regarde une montagne lointaine). Vois si tu repères ainsi plus tôt un mouvement sur les bords, et si ta main se relâche. C’est une tradition, pas un mécanisme mesuré.',
        'pt': 'Sob pressão, a atenção pode se estreitar — os olhos se cravam na mira e as bordas da tela parecem sumir. O olhar suave e amplo é uma velha orientação das artes marciais (no kendo, “enzan no metsuke” — olhar como se fosse para uma montanha distante). Veja se assim você percebe antes o movimento nas bordas e se a mão se solta. É uma tradição, não um mecanismo medido.',
    },
    'guide.periphery.instruction': {
        'sk': 'Keď zamieriš cez optiku, neprepichuj cieľ očami. Vnímaj celú šírku monitora. Zameriavač ovládaš periférnym citom, ruka drží myš/gamepad ľahko ako vtáča.',
        'en': "When you aim down sights, don't stare through the target. Take in the full width of the monitor. Feel the crosshair with your peripheral awareness, and hold the mouse/pad as lightly as a small bird.",
        'ja': 'スコープを覗くとき、目で標的を突き刺すようにしないでください。モニター全体を感じ取りましょう。照準は周辺視野の感覚で捉え、手は小鳥を持つようにマウスやパッドを軽く握ります。',
        'zh': '开镜瞄准时，不要死死盯着目标看穿过去。把整个显示器的宽度都纳入视野。用周边感知去"感受"准星，握持鼠标或手柄要像握着一只小鸟一样轻柔。',
        'ru': 'Когда целишься, не смотри сквозь цель. Охвати взглядом всю ширину монитора. Ощути прицел периферийным вниманием и держи мышь/геймпад так легко, как маленькую птицу.',
        'es': 'Cuando apuntas, no mires fijamente a través del objetivo. Abarca todo el ancho del monitor. Siente la mira con tu conciencia periférica, y sujeta el ratón/mando tan ligero como un pajarito.',
        'de': 'Wenn du zielst, starre nicht durch das Ziel hindurch. Nimm die volle Breite des Monitors wahr. Spüre das Fadenkreuz mit deiner peripheren Wahrnehmung und halte Maus/Pad so leicht wie einen kleinen Vogel.',
        'fr': "Quand tu vises, ne fixe pas à travers la cible. Embrasse toute la largeur de l'écran. Ressens le viseur avec ta conscience périphérique, et tiens la souris/manette aussi légèrement qu'un petit oiseau.",
        'pt': 'Ao mirar, não fique olhando através do alvo. Abrace toda a largura do monitor. Sinta a mira com sua consciência periférica e segure o mouse/controle tão levemente quanto um passarinho.',
    },
    'guide.periphery.sketch_caption': {
        'sk': 'periférne > tunelové videnie',
        'en': 'peripheral > tunnel vision',
        'ja': '周辺視野 > トンネルビジョン',
        'zh': '周边视野 > 隧道视野',
        'ru': 'периферийное > туннельное зрение',
        'es': 'visión periférica > visión de túnel',
        'de': 'peripheres > Tunnelsehen',
        'fr': 'vision périphérique > vision en tunnel',
        'pt': 'visão periférica > visão em túnel',
    },
    'guide.breath.title': {
        'sk': 'Dych',
        'en': 'Breath',
        'ja': '呼吸',
        'zh': '呼吸',
        'ru': 'Дыхание',
        'es': 'Respiración',
        'de': 'Atem',
        'fr': 'Respiration',
        'pt': 'Respiração',
    },
    'guide.breath.trigger': {
        'sk': 'Keď zabudneš vydýchnuť',
        'en': 'When you forget to breathe out',
        'ja': '息を吐くのを忘れているとき',
        'zh': '当你忘了呼气时',
        'ru': 'Когда забываешь выдохнуть',
        'es': 'Cuando te olvidas de exhalar',
        'de': 'Wenn du vergisst auszuatmen',
        'fr': 'Quand tu oublies d’expirer',
        'pt': 'Quando você se esquece de expirar',
    },
    'guide.breath.sketch_caption': {
        'sk': 'nádych – zádrž – výdych',
        'en': 'inhale – hold – exhale',
        'ja': '吸う - 止める - 吐く',
        'zh': '吸气 – 屏息 – 呼气',
        'ru': 'вдох – задержка – выдох',
        'es': 'inhala – retén – exhala',
        'de': 'einatmen – halten – ausatmen',
        'fr': 'inspire – retiens – expire',
        'pt': 'inspire – segure – expire',
    },
    'guide.breath.tech1.name': {
        'sk': 'Fyziologický vzdych (cyclic sighing)',
        'en': 'Physiological sigh (cyclic sighing)',
        'ja': '生理的ため息（サイクリック・サイイング）',
        'zh': '生理性叹息（周期性叹息法）',
        'ru': 'Физиологический вздох (циклическое вздыхание)',
        'es': 'Suspiro fisiológico (suspiro cíclico)',
        'de': 'Physiologisches Seufzen (Cyclic Sighing)',
        'fr': 'Soupir physiologique (cyclic sighing)',
        'pt': 'Suspiro fisiológico (suspiro cíclico)',
    },
    'guide.breath.tech1.steps': {
        'sk': 'Dva rýchle nádychy nosom (jeden plný, druhý okamžitý dotlak) + dlhý, pomalý výdych ústami.',
        'en': 'Two quick inhales through the nose (one full, one short top-up) followed by a long, slow exhale through the mouth.',
        'ja': '鼻から素早く2回吸う（1回目は深く、2回目は瞬時の継ぎ足し）+ 口からゆっくり長く吐く。',
        'zh': '用鼻子快速吸气两次（一次深吸，一次短促补气），随后用嘴巴缓慢地长长呼出。',
        'ru': 'Два быстрых вдоха носом (один полный, один короткий добор) с последующим долгим медленным выдохом через рот.',
        'es': 'Dos inhalaciones rápidas por la nariz (una completa, una corta de refuerzo) seguidas de una exhalación larga y lenta por la boca.',
        'de': 'Zwei kurze Einatmungen durch die Nase (eine volle, eine kurze Nachfüllung), gefolgt von einer langen, langsamen Ausatmung durch den Mund.',
        'fr': "Deux inspirations rapides par le nez (une complète, une courte de renfort) suivies d'une longue expiration lente par la bouche.",
        'pt': 'Duas inspirações rápidas pelo nariz (uma completa, uma curta de reforço) seguidas de uma expiração longa e lenta pela boca.',
    },
    'guide.breath.tech1.why': {
        'sk': 'Tep sa pri nádychu mierne zrýchli a pri výdychu spomalí (Lehrer & Gevirtz 2014, v zdrojoch nižšie) — preto je dôležitý hlavne dlhý výdych. Dvojitý nádych k vzdychu patrí; skús, či sa ti po ňom ľahšie vydýchne do konca. Robí sa po prehratom súboji alebo počas killcamu.',
        'en': 'Your heart speeds up a little on each in-breath and slows on each out-breath (Lehrer & Gevirtz 2014, in the sources below) — so the long exhale is the part that matters most. The double inhale is part of the sigh; see whether it makes a full exhale easier for you. Do it after a lost fight or during a killcam.',
        'ja': '心拍は息を吸うと少し速くなり、吐くと遅くなります（Lehrer & Gevirtz 2014、下の出典を参照）— だから大事なのは、まず長く吐くことです。2回吸うのはため息の一部です。そのあと最後まで吐き切りやすくなるか試してみてください。撃ち合いに負けたあとや、キルカメラの間に行います。',
        'zh': '吸气时心率会略微加快，呼气时会放慢（Lehrer & Gevirtz 2014，见下方参考来源）——所以最关键的是那口长长的呼气。两次吸气是叹息的一部分；试试看做完之后是否更容易把气呼到底。适合在输掉一场对枪后或看击杀回放时做。',
        'ru': 'Пульс на вдохе немного ускоряется, а на выдохе замедляется (Lehrer & Gevirtz 2014, в источниках ниже) — поэтому важнее всего долгий выдох. Двойной вдох — часть вздоха; попробуй, легче ли после него выдохнуть до конца. Делают это после проигранного боя или во время киллкама.',
        'es': 'El pulso se acelera un poco al inhalar y se ralentiza al exhalar (Lehrer & Gevirtz 2014, en las fuentes de abajo) — por eso lo más importante es la exhalación larga. La doble inhalación forma parte del suspiro; prueba si después te resulta más fácil exhalar hasta el final. Se hace tras perder un duelo o durante la killcam.',
        'de': 'Der Puls wird beim Einatmen etwas schneller und beim Ausatmen langsamer (Lehrer & Gevirtz 2014, in den Quellen unten) — deshalb zählt vor allem das lange Ausatmen. Das doppelte Einatmen gehört zum Seufzer; probier, ob du danach leichter ganz ausatmen kannst. Man macht es nach einem verlorenen Gefecht oder während der Killcam.',
        'fr': 'Le pouls accélère légèrement à l’inspiration et ralentit à l’expiration (Lehrer & Gevirtz 2014, dans les sources ci-dessous) — c’est pourquoi c’est surtout la longue expiration qui compte. La double inspiration fait partie du soupir ; vois si, après elle, il t’est plus facile d’expirer jusqu’au bout. À faire après un duel perdu ou pendant une killcam.',
        'pt': 'O coração acelera um pouco a cada inspiração e desacelera a cada expiração (Lehrer & Gevirtz 2014, nas fontes abaixo) — por isso o que mais importa é a expiração longa. A inspiração dupla faz parte do suspiro; veja se depois dela fica mais fácil soltar o ar até o fim. Use depois de perder um duelo ou durante a killcam.',
    },
    'guide.breath.tech2.name': {
        'sk': 'Krabicové dýchanie (box breathing)',
        'en': 'Box breathing',
        'ja': 'ボックス・ブリージング（箱呼吸）',
        'zh': '方块呼吸法',
        'ru': 'Квадратное дыхание',
        'es': 'Respiración cuadrada',
        'de': 'Box-Breathing',
        'fr': 'Respiration carrée',
        'pt': 'Respiração quadrada',
    },
    'guide.breath.tech2.steps': {
        'sk': '4 s nádych – 4 s držanie – 4 s výdych – 4 s držanie.',
        'en': '4 s inhale – 4 s hold – 4 s exhale – 4 s hold.',
        'ja': '4秒吸う - 4秒止める - 4秒吐く - 4秒止める。',
        'zh': '吸气4秒 – 屏息4秒 – 呼气4秒 – 屏息4秒。',
        'ru': 'Вдох 4 с – задержка 4 с – выдох 4 с – задержка 4 с.',
        'es': '4 s inhala – 4 s retén – 4 s exhala – 4 s retén.',
        'de': '4 s einatmen – 4 s halten – 4 s ausatmen – 4 s halten.',
        'fr': '4 s inspire – 4 s retiens – 4 s expire – 4 s retiens.',
        'pt': '4 s inspire – 4 s segure – 4 s expire – 4 s segure.',
    },
    'guide.breath.tech2.why': {
        'sk': 'Pomalé, pravidelné dýchanie sa v štúdiách spája s pokojnejším stavom (prehľad Zaccaro et al. 2018, v zdrojoch nižšie). Krabicové dýchanie 4-4-4-4 je jednoduchý spôsob, ako to tempo udržať, a počítanie dá hlave čo robiť. Hodí sa na dlhšie čakanie v lobby či medzi zápasmi; ak ti zádrž nesedí, skráť ju.',
        'en': 'Slow, steady breathing is linked in studies to a calmer state (the Zaccaro et al. 2018 review, in the sources below). The 4-4-4-4 box is a simple way to keep that pace, and counting gives your mind something to do. Good for longer waits in the lobby or between matches; if a hold feels uncomfortable, shorten it.',
        'ja': 'ゆっくり一定の呼吸は、研究でより穏やかな状態と結びつけられています（Zaccaro ら 2018 のレビュー、下の出典を参照）。4-4-4-4 のボックス呼吸はそのペースを保つ簡単な方法で、数を数えることで頭にもやることができます。ロビーや試合の合間の長めの待ち時間に向いています。息を止めるのがつらければ、短くしてください。',
        'zh': '在研究中，缓慢而有规律的呼吸与更平静的状态相关（Zaccaro et al. 2018 的综述，见下方参考来源）。4-4-4-4 方块呼吸法是保持这种节奏的简单方法，数数也让脑子有事可做。适合在大厅里或比赛之间等待较久时使用；如果屏息让你不舒服，就缩短它。',
        'ru': 'Медленное, ровное дыхание в исследованиях связывают с более спокойным состоянием (обзор Zaccaro et al. 2018, в источниках ниже). Квадратное дыхание 4-4-4-4 — простой способ держать этот темп, а счёт даёт голове занятие. Подходит для долгого ожидания в лобби или между матчами; если задержка тебе неудобна, сократи её.',
        'es': 'En los estudios, la respiración lenta y regular se asocia con un estado más tranquilo (revisión de Zaccaro et al. 2018, en las fuentes de abajo). La respiración cuadrada 4-4-4-4 es una forma sencilla de mantener ese ritmo, y contar le da a la cabeza algo que hacer. Va bien para esperas largas en el lobby o entre partidas; si la retención no te sienta bien, acórtala.',
        'de': 'Langsames, gleichmäßiges Atmen wird in Studien mit einem ruhigeren Zustand in Verbindung gebracht (Übersicht Zaccaro et al. 2018, in den Quellen unten). Das Box-Breathing 4-4-4-4 ist ein einfacher Weg, dieses Tempo zu halten, und das Zählen gibt dem Kopf etwas zu tun. Passt für längeres Warten in der Lobby oder zwischen Matches; wenn dir das Halten nicht liegt, verkürze es.',
        'fr': 'Dans les études, une respiration lente et régulière est associée à un état plus calme (la revue de Zaccaro et al. 2018, dans les sources ci-dessous). La respiration carrée 4-4-4-4 est une façon simple de garder ce rythme, et compter donne à ta tête de quoi s’occuper. Elle convient aux longues attentes dans le lobby ou entre deux matchs ; si la rétention ne te convient pas, raccourcis-la.',
        'pt': 'Em estudos, a respiração lenta e regular aparece associada a um estado mais calmo (revisão de Zaccaro et al. 2018, nas fontes abaixo). A respiração quadrada 4-4-4-4 é um jeito simples de manter esse ritmo, e contar dá à cabeça algo para fazer. Serve para esperas mais longas no lobby ou entre partidas; se segurar o ar não for confortável, encurte a pausa.',
    },
    'guide.philosophy.title': {
        'sk': 'Plť cez rieku',
        'en': 'A raft across the river',
        'ja': '川を渡る筏',
        'zh': '渡河的木筏',
        'ru': 'Плот через реку',
        'es': 'Una balsa para cruzar el río',
        'de': 'Ein Floß über den Fluss',
        'fr': 'Un radeau pour traverser la rivière',
        'pt': 'Uma jangada para atravessar o rio',
    },
    'guide.philosophy.trigger': {
        'sk': 'Filozofia, hranice nástroja a zdroje',
        'en': 'Philosophy, the tool’s limits & sources',
        'ja': '哲学、道具の限界、出典',
        'zh': '理念、工具的局限与参考来源',
        'ru': 'Философия, границы инструмента и источники',
        'es': 'Filosofía, límites de la herramienta y fuentes',
        'de': 'Philosophie, Grenzen des Werkzeugs und Quellen',
        'fr': 'Philosophie, limites de l’outil et sources',
        'pt': 'Filosofia, limites da ferramenta e fontes',
    },
    'guide.philosophy.sketch_caption': {
        'sk': 'prst ukazuje na mesiac',
        'en': 'the finger points at the moon',
        'ja': '指は月を指す',
        'zh': '手指指向月亮',
        'ru': 'палец указывает на луну',
        'es': 'el dedo señala a la luna',
        'de': 'der Finger zeigt auf den Mond',
        'fr': 'le doigt qui montre la lune',
        'pt': 'o dedo aponta para a lua',
    },
    'guide.philosophy.block1_title': {
        'sk': 'Prečo to sedí s tradíciou',
        'en': 'Why it fits the tradition',
        'ja': 'なぜ伝統と矛盾しないのか',
        'zh': '为何这与传统相合而非相悖',
        'ru': 'Почему это соответствует традиции, а не противоречит ей',
        'es': 'Por qué encaja con la tradición',
        'de': 'Warum es zur Tradition passt',
        'fr': "Pourquoi cela s'accorde avec la tradition",
        'pt': 'Por que isso se encaixa na tradição',
    },
    'guide.philosophy.block1_text': {
        'sk': 'Zen aj bojové umenia sú pragmatické: nezáleží, či je nástroj drevená palica alebo pár riadkov kódu, záleží na vzťahu k nemu. V budhizme sa tomu hovorí upája — šikovné prostriedky. Ak ťa hra stiahne do napätia, zvuk slúži ako klepnutie bambusovej palice (keisaku), ktorou učiteľ jemne prebudí driemajúcu myseľ. A vedomé uvoľnenie čeľuste pri každom prebití je kata — mechanické opakovanie, z ktorého sa časom stane wu wei: prsty a reflexy konajú bez toho, aby ego tlačilo na výsledok.',
        'en': "Zen and the martial arts are both pragmatic: it doesn't matter whether the tool is a wooden stick or a few lines of code - what matters is your relationship to it. Buddhism calls this upaya, skillful means. If the game pulls you into tension, the sound acts like a keisaku - the bamboo stick a teacher taps a dozing student with. And consciously releasing your jaw on every reload is a kata - mechanical repetition that, over time, becomes wu wei: fingers and reflexes acting without ego pushing for a result.",
        'ja': '禅も武道も実用的です - 道具が木の棒であろうとコードであろうと関係なく、大切なのはそれとの関係性です。仏教ではこれを「方便（ほうべん）」と呼びます。ゲームが緊張に引き込むなら、音は「警策（けいさく）」- 居眠りする修行者を優しく起こす竹の棒のように働きます。そしてリロードのたびに顎を意識的に緩めることは「型」- やがて「無為（むい）」になる機械的な反復です：指と反射が、結果に対する我執なしに動くようになります。',
        'zh': '禅与武术都是务实的：工具是一根木棍还是几行代码并不重要 - 重要的是你与它的关系。佛教称这种智慧的方便法门为"upaya"。如果游戏把你拉入紧张状态，声音就像"警策"（keisaku）- 老师用来轻拍打瞌睡学生的竹棒。每次换弹时有意识地放松下颌，就是一种"型"（kata）- 机械性的重复，久而久之会转化为"无为"（wu wei）：手指与反射自然行动，不再被自我推着去追求结果。',
        'ru': 'Дзен и боевые искусства прагматичны: неважно, палка это деревянная или несколько строк кода - важны твои отношения с инструментом. Буддизм называет это упайя, искусные средства. Если игра затягивает тебя в напряжение, звук действует как кэйсаку - бамбуковая палка, которой учитель слегка ударяет задремавшего ученика. А осознанное расслабление челюсти при каждой перезарядке - это ката: механическое повторение, которое со временем становится у-вэй: пальцы и рефлексы действуют без давления эго ради результата.',
        'es': 'El zen y las artes marciales son pragmáticos: no importa si la herramienta es un palo de madera o unas líneas de código - lo que importa es tu relación con ella. El budismo llama a esto upaya, medios hábiles. Si el juego te arrastra a la tensión, el sonido actúa como un keisaku - el bastón de bambú con el que un maestro golpea suavemente a un alumno adormilado. Y soltar conscientemente la mandíbula en cada recarga es un kata - repetición mecánica que, con el tiempo, se convierte en wu wei: los dedos y los reflejos actúan sin que el ego empuje por un resultado.',
        'de': 'Zen und Kampfkunst sind beide pragmatisch: Es spielt keine Rolle, ob das Werkzeug ein Holzstock oder ein paar Zeilen Code ist - was zählt, ist deine Beziehung dazu. Der Buddhismus nennt das upaya, geschickte Mittel. Wenn das Spiel dich in Anspannung zieht, wirkt der Ton wie ein Keisaku - der Bambusstock, mit dem ein Lehrer einen einnickenden Schüler sanft antippt. Und das bewusste Lösen deines Kiefers bei jedem Nachladen ist eine Kata - mechanische Wiederholung, die mit der Zeit zu Wu Wei wird: Finger und Reflexe handeln, ohne dass das Ego auf ein Ergebnis drängt.',
        'fr': "Le zen et les arts martiaux sont tous deux pragmatiques : peu importe que l'outil soit un bâton de bois ou quelques lignes de code - ce qui compte, c'est ta relation avec lui. Le bouddhisme appelle cela upaya, les moyens habiles. Si le jeu t'entraîne dans la tension, le son agit comme un keisaku - le bâton de bambou avec lequel un maître tape doucement un élève somnolent. Et relâcher consciemment ta mâchoire à chaque rechargement est un kata - une répétition mécanique qui, avec le temps, devient wu wei : les doigts et les réflexes agissent sans que l'ego ne pousse vers un résultat.",
        'pt': 'O zen e as artes marciais são ambos pragmáticos: não importa se a ferramenta é um bastão de madeira ou algumas linhas de código - o que importa é a sua relação com ela. O budismo chama isso de upaya, meios hábeis. Se o jogo te puxa para a tensão, o som age como um keisaku - o bastão de bambu com que um mestre toca de leve um aluno cochilando. E soltar conscientemente a mandíbula a cada recarga é um kata - repetição mecânica que, com o tempo, se torna wu wei: os dedos e reflexos agem sem que o ego empurre por um resultado.',
    },
    'guide.philosophy.block2_title': {
        'sk': 'Plť, nie domov',
        'en': 'A raft, not a home',
        'ja': '筏であって、住処ではない',
        'zh': '木筏，而非归宿',
        'ru': 'Плот, а не дом',
        'es': 'Una balsa, no un hogar',
        'de': 'Ein Floß, kein Zuhause',
        'fr': 'Un radeau, pas un foyer',
        'pt': 'Uma jangada, não um lar',
    },
    'guide.philosophy.block2_text': {
        'sk': 'Stará budhistická metafora hovorí: keď prekročíš rieku na plti, nenosíš si ju ďalej na chrbte po súši — necháš ju na brehu. Táto appka je presne taká plť. Problém by nastal vtedy, keby sa ti telo bez nej vôbec nedarilo uvoľniť alebo keby mal softvér meditovať za teba. V súlade to je vtedy, keď ju vnímaš ako tréningové kolieska: časom si telo možno začne na výdych a uvoľnenú čeľusť spomínať samo — a vtedy môžeš hlas aj zvuk nechať potichu ustúpiť do pozadia.',
        'en': 'An old Buddhist metaphor: once you’ve crossed the river on a raft, you don’t keep carrying it on your back down the road — you leave it on the bank. This app is exactly that raft. It would become a problem if you couldn’t relax your body at all without it running, or if you expected the software to meditate for you. It’s aligned when you treat it as training wheels: with time your body may start recalling the exhale and the loose jaw on its own — and then you can let the voice and sound quietly fade into the background.',
        'ja': '古い仏教のたとえがあります。筏で川を渡ったら、その筏を背負ったまま陸を歩き続けはしない — 岸に置いていく。このアプリはまさにその筏です。問題になるのは、これなしではまったく体をゆるめられなくなったとき、あるいはソフトウェアが代わりに瞑想してくれると期待したときです。うまく付き合えているのは、補助輪として使っているときです。やがて体が、長く吐く息やゆるんだ顎を自分から思い出すようになるかもしれません — そうしたら、音声も効果音も静かに背景へ退かせていいのです。',
        'zh': '一个古老的佛教比喻说：乘筏渡过河之后，你不会把木筏背在背上继续走陆路——你会把它留在岸边。这个应用正是这样一只木筏。如果没有它你就完全无法放松身体，或者你指望软件替你冥想，那就成了问题。当你把它当作学骑车时的辅助轮，才算用得其所：随着时间推移，身体也许会自己记起呼气和放松的下颌——那时你就可以让语音和音效悄悄退到幕后。',
        'ru': 'Старая буддийская метафора гласит: переправившись через реку на плоту, ты не несёшь его дальше по суше на спине — ты оставляешь его на берегу. Это приложение — именно такой плот. Проблема возникла бы, если бы без него тело вообще не удавалось расслабить или если бы программа должна была медитировать за тебя. Всё на своём месте, когда ты воспринимаешь его как тренировочные колёсики: со временем тело, возможно, начнёт само вспоминать о выдохе и расслабленной челюсти — и тогда голос и звук можно тихо отпустить на задний план.',
        'es': 'Una vieja metáfora budista dice: cuando cruzas el río en una balsa, no sigues cargándola a la espalda por tierra firme — la dejas en la orilla. Esta app es exactamente esa balsa. El problema llegaría si sin ella no supieras relajar el cuerpo en absoluto, o si esperaras que el software meditara por ti. Todo encaja cuando la ves como los ruedines de una bici: con el tiempo, quizá tu cuerpo empiece a recordar por sí solo la exhalación y la mandíbula suelta — y entonces puedes dejar que la voz y el sonido pasen en silencio a un segundo plano.',
        'de': 'Eine alte buddhistische Metapher sagt: Wenn du den Fluss auf einem Floß überquert hast, trägst du es an Land nicht auf dem Rücken weiter — du lässt es am Ufer. Diese App ist genau so ein Floß. Ein Problem wäre es, wenn du ohne sie deinen Körper überhaupt nicht mehr lockern könntest oder wenn du erwarten würdest, dass die Software für dich meditiert. Stimmig ist es, wenn du sie als Stützräder siehst: Mit der Zeit erinnert sich dein Körper vielleicht von selbst an das Ausatmen und den lockeren Kiefer — und dann kannst du Stimme und Ton leise in den Hintergrund treten lassen.',
        'fr': 'Une vieille métaphore bouddhiste dit : une fois la rivière traversée sur un radeau, tu ne continues pas à le porter sur ton dos sur la terre ferme — tu le laisses sur la rive. Cette app est exactement ce radeau. Le problème viendrait si tu ne savais plus du tout détendre ton corps sans elle, ou si tu attendais que le logiciel médite à ta place. Tout est en accord quand tu la vois comme les petites roues d’un vélo d’enfant : avec le temps, ton corps se souviendra peut-être tout seul de l’expiration et de la mâchoire relâchée — et alors tu pourras laisser la voix et le son s’effacer doucement à l’arrière-plan.',
        'pt': 'Uma antiga metáfora budista diz: depois de atravessar o rio numa jangada, você não continua carregando-a nas costas por terra — você a deixa na margem. Este app é exatamente essa jangada. O problema seria se você não conseguisse soltar o corpo de jeito nenhum sem ele, ou se esperasse que o software meditasse por você. Está em harmonia quando você o vê como as rodinhas de uma bicicleta: com o tempo, o corpo talvez comece a se lembrar sozinho da expiração e da mandíbula solta — e aí você pode deixar a voz e o som recuarem em silêncio para o fundo.',
    },
    'guide.philosophy.block3_title': {
        'sk': 'Meč, ktorý berie život vs. meč, ktorý dáva život',
        'en': 'The sword that takes life vs. the sword that gives life',
        'ja': '命を奪う剣、命を活かす剣',
        'zh': '夺命之剑 与 活人之剑',
        'ru': 'Меч, отнимающий жизнь, против меча, дающего жизнь',
        'es': 'La espada que quita la vida frente a la espada que da la vida',
        'de': 'Das Schwert, das Leben nimmt, gegen das Schwert, das Leben gibt',
        'fr': "L'épée qui ôte la vie contre l'épée qui donne la vie",
        'pt': 'A espada que tira a vida versus a espada que dá a vida',
    },
    'guide.philosophy.block3_text': {
        'sk': 'V japonskom kendžucu sa rozlišuje sacunintō — meč použitý len na drvenie súpera, dominanciu a ego — a kacuninken — meč, ktorým premáhaš vlastný strach a hnev. Ak niekto vezme uvoľnenie tela len ako „bio-hack na výhru“, skôr či neskôr narazí na strop: pri každej neférovej smrti nastúpi frustrácia, lebo hlava zostala toxická. Telo a emócie sú spojené nádoby — telo ťažko zostane naozaj uvoľnené, keď v ňom vrie slepá zlosť. Aj keď niekto začne z čisto sebeckého dôvodu (chcem vyhrávať), samotná prax ho môže nenápadne viesť k tomu, aby skrotil vlastné ego.',
        'en': 'In Japanese kenjutsu, a distinction is made between satsujinken - a sword used purely to crush an opponent, for dominance and ego - and katsujinken - a sword used to overcome your own fear and anger. If someone treats bodily release as a pure "win bio-hack," they\'ll sooner or later hit a ceiling: every unfair death still triggers frustration, because the mind stayed toxic. Body and emotion are connected vessels - it\'s hard to be truly relaxed and blindly furious at the same time. Even someone who starts for a purely selfish reason (I want to win) may find the practice itself quietly leading them to tame their own ego.',
        'ja': '日本の剣術では、殺人刀（せつにんとう）— 相手を打ち砕き、支配し、エゴを満たすためだけの剣 — と、活人剣（かつにんけん）— 自分の恐れや怒りに打ち勝つための剣 — が区別されます。体をゆるめることを「勝つためのバイオハック」としか見ないなら、遅かれ早かれ天井にぶつかります。理不尽なデスのたびに苛立ちが湧いてくる — 頭の中が毒されたままだからです。体と感情はつながった器です — 本当にゆるんでいながら、同時に盲目的な怒りに満ちているのは難しいものです。まったく利己的な理由（勝ちたい）から始めた人でも、実践そのものが、いつのまにか自分のエゴを手なずける方向へ導いてくれるかもしれません。',
        'zh': '日本剑术里区分两种剑：杀人刀（satsujintō）——只用来碾压对手、追求支配与小我的剑；以及活人剑（katsujinken）——用来战胜自己恐惧与愤怒的剑。如果有人只把放松身体当作“赢游戏的生物黑客技巧”，迟早会碰到天花板：每一次不公平的阵亡依然会引发挫败感，因为头脑仍是有毒的。身体和情绪是连通的容器——很难既真正放松，又满怀盲目的怒火。即使有人出于纯粹自私的理由开始（我想赢），练习本身也可能悄悄引导他驯服自己的小我。',
        'ru': 'В японском кэндзюцу различают сацунинто — меч, которым лишь сокрушают соперника ради доминирования и эго, — и кацунинкэн — меч, которым преодолевают собственный страх и гнев. Если кто-то воспринимает расслабление тела лишь как «био-хак для победы», рано или поздно он упрётся в потолок: при каждой нечестной смерти приходит фрустрация, потому что голова осталась токсичной. Тело и эмоции — сообщающиеся сосуды: телу трудно оставаться по-настоящему расслабленным, когда в нём кипит слепая злость. Даже если кто-то начинает из чисто эгоистичной причины (хочу побеждать), сама практика может незаметно привести его к тому, чтобы обуздать собственное эго.',
        'es': 'En el kenjutsu japonés se distingue entre el satsunintō — la espada usada solo para aplastar al rival, por dominio y ego — y el katsuninken — la espada con la que vences tu propio miedo y tu ira. Si alguien toma la relajación del cuerpo solo como un «biohack para ganar», tarde o temprano chocará con un techo: con cada muerte injusta llegará la frustración, porque la cabeza siguió tóxica. Cuerpo y emociones son vasos comunicantes — es difícil que el cuerpo siga de verdad relajado mientras hierve de rabia ciega. Aunque alguien empiece por un motivo puramente egoísta (quiero ganar), la propia práctica puede llevarlo discretamente a domar su propio ego.',
        'de': 'Im japanischen Kenjutsu unterscheidet man Satsujintō — das Schwert, das nur dazu dient, den Gegner zu zermalmen, für Dominanz und Ego — und Katsujinken — das Schwert, mit dem du deine eigene Angst und Wut überwindest. Wer das Lockern des Körpers nur als „Bio-Hack zum Gewinnen“ nimmt, stößt früher oder später an eine Decke: Bei jedem unfairen Tod kommt Frust auf, weil der Kopf toxisch geblieben ist. Körper und Gefühle sind kommunizierende Röhren — es ist schwer, wirklich locker und zugleich voll blinder Wut zu sein. Auch wenn jemand aus einem rein egoistischen Grund anfängt (ich will gewinnen), kann ihn die Praxis selbst unauffällig dahin führen, das eigene Ego zu zähmen.',
        'fr': 'Dans le kenjutsu japonais, on distingue le satsujintō — l’épée qui ne sert qu’à écraser l’adversaire, pour la domination et l’ego — et le katsujinken — l’épée avec laquelle tu vaincs ta propre peur et ta colère. Si quelqu’un prend la détente du corps uniquement comme un « bio-hack pour gagner », il se heurtera tôt ou tard à un plafond : à chaque mort injuste, la frustration revient, parce que la tête est restée toxique. Le corps et les émotions sont des vases communicants — un corps reste difficilement détendu quand une colère aveugle bouillonne en lui. Même si quelqu’un commence pour une raison purement égoïste (je veux gagner), la pratique elle-même peut l’amener discrètement à apprivoiser son propre ego.',
        'pt': 'No kenjutsu japonês, há uma distinção entre o satsunintō — a espada usada só para esmagar o adversário, por dominância e ego — e o katsuninken — a espada com que você vence o próprio medo e a própria raiva. Se alguém toma o relaxamento do corpo só como um “bio-hack para vencer”, cedo ou tarde bate no teto: a cada morte injusta vem a frustração, porque a cabeça continuou tóxica. Corpo e emoções são vasos comunicantes — é difícil o corpo continuar realmente relaxado enquanto ferve de raiva cega. Mesmo que alguém comece por um motivo puramente egoísta (quero ganhar), a própria prática pode, sem alarde, levá-lo a domar o próprio ego.',
    },
    'guide.philosophy.sources_title': {
        'sk': 'Zdroje',
        'en': 'Sources',
        'ja': '出典',
        'zh': '参考来源',
        'ru': 'Источники',
        'es': 'Fuentes',
        'de': 'Quellen',
        'fr': 'Sources',
        'pt': 'Fontes',
    },
    'sfx.zen.earth_thud': {
        'sk': 'Zemitý dopad',
        'en': 'Earthy thud',
        'ja': '大地の衝撃音',
        'zh': '泥土般的撞击声',
        'ru': 'Земляной удар',
        'es': 'Impacto terroso',
        'de': 'Erdiger Aufprall',
        'fr': 'Impact terreux',
        'pt': 'Impacto terroso',
    },
    'sfx.zen.wood_temple_block': {
        'sk': 'Drevený blok',
        'en': 'Wood block',
        'ja': '木魚',
        'zh': '木鱼',
        'ru': 'Деревянный блок',
        'es': 'Bloque de madera',
        'de': 'Holzblock',
        'fr': 'Bloc de bois',
        'pt': 'Bloco de madeira',
    },
    'sfx.zen.zen_singing_bowl': {
        'sk': 'Tibetská miska',
        'en': 'Singing bowl',
        'ja': 'シンギングボウル',
        'zh': '颂钵',
        'ru': 'Тибетская чаша',
        'es': 'Cuenco tibetano',
        'de': 'Klangschale',
        'fr': 'Bol tibétain',
        'pt': 'Tigela tibetana',
    },
    'sfx.zen.soft_breath_chime': {
        'sk': 'Dych a cinknutie',
        'en': 'Breath and chime',
        'ja': '呼吸とチャイム',
        'zh': '呼吸与铃声',
        'ru': 'Дыхание и колокольчик',
        'es': 'Respiración y campanilla',
        'de': 'Atem und Glöckchen',
        'fr': 'Souffle et carillon',
        'pt': 'Respiração e sino',
    },
    'sfx.modern.mech_bass_thump': {
        'sk': 'Basový úder',
        'en': 'Bass thump',
        'ja': 'ベースの一撃',
        'zh': '低音重击',
        'ru': 'Басовый удар',
        'es': 'Golpe de bajo',
        'de': 'Bass-Schlag',
        'fr': 'Coup de basse',
        'pt': 'Batida grave',
    },
    'sfx.modern.sfx_click_reload': {
        'sk': 'Magnetické cvaknutie',
        'en': 'Magnetic click',
        'ja': 'マグネティック・クリック',
        'zh': '磁吸咔哒声',
        'ru': 'Магнитный щелчок',
        'es': 'Clic magnético',
        'de': 'Magnetisches Klicken',
        'fr': 'Clic magnétique',
        'pt': 'Clique magnético',
    },
    'sfx.modern.sfx_lock_ping': {
        'sk': 'Krátky ping',
        'en': 'Short ping',
        'ja': '短いピン音',
        'zh': '短促提示音',
        'ru': 'Короткий пинг',
        'es': 'Pitido corto',
        'de': 'Kurzer Ping',
        'fr': 'Bip court',
        'pt': 'Bipe curto',
    },
    'sfx.modern.vent_release': {
        'sk': 'Ventil',
        'en': 'Vent',
        'ja': '圧力弁',
        'zh': '泄压阀',
        'ru': 'Клапан',
        'es': 'Válvula',
        'de': 'Ventil',
        'fr': 'Soupape',
        'pt': 'Válvula',
    },
    'sfx.log.downloaded': {
        'sk': 'SFX: {label} stiahnuté (CC0, Kenney).',
        'en': 'SFX: {label} downloaded (CC0, Kenney).',
        'ja': 'SFX: {label} をダウンロードしました（CC0, Kenney）。',
        'zh': '音效：{label} 下载完成（CC0，Kenney）。',
        'ru': 'SFX: {label} загружен (CC0, Kenney).',
        'es': 'SFX: {label} descargado (CC0, Kenney).',
        'de': 'SFX: {label} heruntergeladen (CC0, Kenney).',
        'fr': 'SFX : {label} téléchargé (CC0, Kenney).',
        'pt': 'SFX: {label} baixado (CC0, Kenney).',
    },
    'sfx.log.synth': {
        'sk': 'SFX: {label} — vygenerované lokálne.',
        'en': 'SFX: {label} - generated locally.',
        'ja': 'SFX: {label} - ローカルで生成しました。',
        'zh': '音效：{label} - 已在本地生成。',
        'ru': 'SFX: {label} - сгенерирован локально.',
        'es': 'SFX: {label} - generado localmente.',
        'de': 'SFX: {label} - lokal generiert.',
        'fr': 'SFX : {label} - généré localement.',
        'pt': 'SFX: {label} - gerado localmente.',
    },
    'sfx.log.synth_fallback': {
        'sk': 'SFX: {label} — sťahovanie zlyhalo, vygenerované lokálne.',
        'en': 'SFX: {label} - download failed, generated locally instead.',
        'ja': 'SFX: {label} - ダウンロードに失敗したため、ローカルで生成しました。',
        'zh': '音效：{label} - 下载失败，已改为在本地生成。',
        'ru': 'SFX: {label} - загрузка не удалась, сгенерирован локально.',
        'es': 'SFX: {label} - la descarga falló, generado localmente en su lugar.',
        'de': 'SFX: {label} - Download fehlgeschlagen, stattdessen lokal generiert.',
        'fr': 'SFX : {label} - échec du téléchargement, généré localement à la place.',
        'pt': 'SFX: {label} - falha no download, gerado localmente em vez disso.',
    },
    'sfx.log.failed': {
        'sk': 'SFX: {label} sa nepodarilo pripraviť ({err}).',
        'en': "SFX: couldn't prepare {label} ({err}).",
        'ja': 'SFX: {label} の準備に失敗しました（{err}）。',
        'zh': '音效：无法准备 {label}（{err}）。',
        'ru': 'SFX: не удалось подготовить {label} ({err}).',
        'es': 'SFX: no se pudo preparar {label} ({err}).',
        'de': 'SFX: {label} konnte nicht vorbereitet werden ({err}).',
        'fr': 'SFX : impossible de préparer {label} ({err}).',
        'pt': 'SFX: não foi possível preparar {label} ({err}).',
    },
    # The voice words of the four categories (after 0.3): every cue starts
    # with the exhale - a long exhale fits any moment - followed by the same
    # body word as up to 0.3; the breath slot says "long exhale". Sk/cs
    # keep the English words on purpose (see VOICE_HINTS in
    # settings_model). Each one is short enough to say in about a second
    # and a half and never commands a state ("relax", "calm down" -
    # tests/test_cue_words.py). An existing profile with the old word gets
    # the new one when the settings are loaded, and so does a profile code
    # from before 0.3.1 when it is imported
    # (`settings_model.migrate_profile_texts`).
    'slot.default.grounding': {
        'sk': 'Exhale, grounded',
        'en': 'Exhale, grounded',
        'ja': '息を吐いて、重心',
        'zh': '呼气，落地',
        'ru': 'Выдох, опора',
        'es': 'Exhala, pies en la tierra',
        'de': 'Ausatmen, geerdet',
        'fr': 'Expire, ancré',
        'pt': 'Expira, aterrado',
    },
    'slot.default.jaw': {
        'sk': 'Exhale, jaw',
        'en': 'Exhale, jaw',
        'ja': '息を吐いて、顎',
        'zh': '呼气，牙关',
        'ru': 'Выдох, челюсть',
        'es': 'Exhala, mandíbula',
        'de': 'Ausatmen, Kiefer',
        'fr': 'Expire, mâchoire',
        'pt': 'Expira, mandíbula',
    },
    'slot.default.release': {
        'sk': 'Exhale, release',
        'en': 'Exhale, release',
        'ja': '息を吐いて、解放',
        'zh': '呼气，松开',
        'ru': 'Выдох, отпусти',
        'es': 'Exhala, suelta',
        'de': 'Ausatmen, loslassen',
        'fr': 'Expire, relâche',
        'pt': 'Expira, solta',
    },
    'slot.default.breath': {
        'sk': 'Long exhale',
        'en': 'Long exhale',
        'ja': '息を長く吐いて',
        'zh': '长长地呼气',
        'ru': 'Долгий выдох',
        'es': 'Exhala largo',
        'de': 'Lang ausatmen',
        'fr': 'Expire longuement',
        'pt': 'Expiração longa',
    },
    'lang.zh': {
        'sk': 'Čínština (zjednodušená)',
        'en': 'Chinese (Simplified)',
        'ja': '中国語（簡体字）',
        'zh': '简体中文',
        'ru': 'Китайский (упрощённый)',
        'es': 'Chino (simplificado)',
        'de': 'Chinesisch (vereinfacht)',
        'fr': 'Chinois (simplifié)',
        'pt': 'Chinês (simplificado)',
    },
    'lang.ru': {
        'sk': 'Ruština',
        'en': 'Russian',
        'ja': 'ロシア語',
        'zh': '俄语',
        'ru': 'Русский',
        'es': 'Ruso',
        'de': 'Russisch',
        'fr': 'Russe',
        'pt': 'Russo',
    },
    'lang.es': {
        'sk': 'Španielčina',
        'en': 'Spanish',
        'ja': 'スペイン語',
        'zh': '西班牙语',
        'ru': 'Испанский',
        'es': 'Español',
        'de': 'Spanisch',
        'fr': 'Espagnol',
        'pt': 'Espanhol',
    },
    'lang.de': {
        'sk': 'Nemčina',
        'en': 'German',
        'ja': 'ドイツ語',
        'zh': '德语',
        'ru': 'Немецкий',
        'es': 'Alemán',
        'de': 'Deutsch',
        'fr': 'Allemand',
        'pt': 'Alemão',
    },
    'lang.fr': {
        'sk': 'Francúzština',
        'en': 'French',
        'ja': 'フランス語',
        'zh': '法语',
        'ru': 'Французский',
        'es': 'Francés',
        'de': 'Französisch',
        'fr': 'Français',
        'pt': 'Francês',
    },
    'lang.pt': {
        'sk': 'Portugalčina (Brazília)',
        'en': 'Portuguese (Brazil)',
        'ja': 'ポルトガル語（ブラジル）',
        'zh': '葡萄牙语（巴西）',
        'ru': 'Португальский (Бразилия)',
        'es': 'Portugués (Brasil)',
        'de': 'Portugiesisch (Brasilien)',
        'fr': 'Portugais (Brésil)',
        'pt': 'Português (Brasil)',
    },
    # Czech and Bulgarian (0.2) - the log „Jazyk rozhrania prepnuty na: …“
    # reads `lang.{kod}` for every language in LANGUAGES (the cs/bg texts
    # are in i18n_cs_bg.py)
    'lang.cs': {
        'sk': 'Čeština',
        'en': 'Czech',
        'ja': 'チェコ語',
        'zh': '捷克语',
        'ru': 'Чешский',
        'es': 'Checo',
        'de': 'Tschechisch',
        'fr': 'Tchèque',
        'pt': 'Tcheco',
    },
    'lang.bg': {
        'sk': 'Bulharčina',
        'en': 'Bulgarian',
        'ja': 'ブルガリア語',
        'zh': '保加利亚语',
        'ru': 'Болгарский',
        'es': 'Búlgaro',
        'de': 'Bulgarisch',
        'fr': 'Bulgare',
        'pt': 'Búlgaro',
    },
}

# --------------------------------------------------------------------------
# PHASE 3: in-game HUD, labels of visuals and monitor selection.
# sk/en are translated by hand; the other languages get the English
# version for now (better than the Slovak fallback) - for later
# translation like the rest of the file, see the note in the module
# header.
# --------------------------------------------------------------------------

STRINGS.update({
    'overlay.caption.grounding': {
        'sk': 'PUSTI VÁHU DOLE',
        'en': 'DROP YOUR WEIGHT',
        'ja': 'DROP YOUR WEIGHT',
        'zh': 'DROP YOUR WEIGHT',
        'ru': 'DROP YOUR WEIGHT',
        'es': 'DROP YOUR WEIGHT',
        'de': 'DROP YOUR WEIGHT',
        'fr': 'DROP YOUR WEIGHT',
        'pt': 'DROP YOUR WEIGHT',
    },
    'overlay.caption.jaw': {
        'sk': 'UVOĽNI ČEĽUSŤ',
        'en': 'UNCLENCH YOUR JAW',
        'ja': 'UNCLENCH YOUR JAW',
        'zh': 'UNCLENCH YOUR JAW',
        'ru': 'UNCLENCH YOUR JAW',
        'es': 'UNCLENCH YOUR JAW',
        'de': 'UNCLENCH YOUR JAW',
        'fr': 'UNCLENCH YOUR JAW',
        'pt': 'UNCLENCH YOUR JAW',
    },
    'overlay.caption.release': {
        'sk': 'PUSTI STISK',
        'en': 'LOOSEN YOUR GRIP',
        'ja': 'LOOSEN YOUR GRIP',
        'zh': 'LOOSEN YOUR GRIP',
        'ru': 'LOOSEN YOUR GRIP',
        'es': 'LOOSEN YOUR GRIP',
        'de': 'LOOSEN YOUR GRIP',
        'fr': 'LOOSEN YOUR GRIP',
        'pt': 'LOOSEN YOUR GRIP',
    },
    'overlay.caption.inhale': {
        'sk': 'NÁDYCH',
        'en': 'INHALE',
        'ja': 'INHALE',
        'zh': 'INHALE',
        'ru': 'INHALE',
        'es': 'INHALE',
        'de': 'INHALE',
        'fr': 'INHALE',
        'pt': 'INHALE',
    },
    'overlay.caption.exhale': {
        'sk': 'VÝDYCH',
        'en': 'EXHALE',
        'ja': 'EXHALE',
        'zh': 'EXHALE',
        'ru': 'EXHALE',
        'es': 'EXHALE',
        'de': 'EXHALE',
        'fr': 'EXHALE',
        'pt': 'EXHALE',
    },
    'overlay.monitor.label': {
        'sk': 'Monitor pre vizuály a HUD',
        'en': 'Monitor for visuals and HUD',
        'ja': 'Monitor for visuals and HUD',
        'zh': 'Monitor for visuals and HUD',
        'ru': 'Monitor for visuals and HUD',
        'es': 'Monitor for visuals and HUD',
        'de': 'Monitor for visuals and HUD',
        'fr': 'Monitor for visuals and HUD',
        'pt': 'Monitor for visuals and HUD',
    },
    'overlay.monitor.auto': {
        'sk': 'Automaticky (kde beží hra)',
        'en': 'Automatic (where the game runs)',
        'ja': 'Automatic (where the game runs)',
        'zh': 'Automatic (where the game runs)',
        'ru': 'Automatic (where the game runs)',
        'es': 'Automatic (where the game runs)',
        'de': 'Automatic (where the game runs)',
        'fr': 'Automatic (where the game runs)',
        'pt': 'Automatic (where the game runs)',
    },
    'overlay.monitor.cursor': {
        'sk': 'Kde je kurzor',
        'en': 'Where the cursor is',
        'ja': 'Where the cursor is',
        'zh': 'Where the cursor is',
        'ru': 'Where the cursor is',
        'es': 'Where the cursor is',
        'de': 'Where the cursor is',
        'fr': 'Where the cursor is',
        'pt': 'Where the cursor is',
    },
    'overlay.monitor.primary': {
        'sk': 'Hlavný monitor',
        'en': 'Primary monitor',
        'ja': 'Primary monitor',
        'zh': 'Primary monitor',
        'ru': 'Primary monitor',
        'es': 'Primary monitor',
        'de': 'Primary monitor',
        'fr': 'Primary monitor',
        'pt': 'Primary monitor',
    },
    'overlay.monitor.hint': {
        'sk': 'Pri „Automaticky“ kreslím na tú obrazovku, na ktorej máš práve aktívne okno — teda na tú, kde hráš.',
        'en': 'With “Automatic” I draw on whichever screen holds the active window — the one you are playing on.',
        'ja': 'With “Automatic” the app draws on whichever screen holds the active window - the one you are playing on.',
        'zh': 'With “Automatic” the app draws on whichever screen holds the active window - the one you are playing on.',
        'ru': 'With “Automatic” the app draws on whichever screen holds the active window - the one you are playing on.',
        'es': 'With “Automatic” the app draws on whichever screen holds the active window - the one you are playing on.',
        'de': 'With “Automatic” the app draws on whichever screen holds the active window - the one you are playing on.',
        'fr': 'With “Automatic” the app draws on whichever screen holds the active window - the one you are playing on.',
        'pt': 'With “Automatic” the app draws on whichever screen holds the active window - the one you are playing on.',
    },
    'hud.section_title': {
        'sk': 'HUD tepu a záťaže',
        'en': 'Heart rate & load HUD',
        'ja': 'Heart rate & load HUD',
        'zh': 'Heart rate & load HUD',
        'ru': 'Heart rate & load HUD',
        'es': 'Heart rate & load HUD',
        'de': 'Heart rate & load HUD',
        'fr': 'Heart rate & load HUD',
        'pt': 'Heart rate & load HUD',
    },
    'hud.enable': {
        'sk': 'Zobraziť HUD v hre',
        'en': 'Show HUD in game',
        'ja': 'Show HUD in game',
        'zh': 'Show HUD in game',
        'ru': 'Show HUD in game',
        'es': 'Show HUD in game',
        'de': 'Show HUD in game',
        'fr': 'Show HUD in game',
        'pt': 'Show HUD in game',
    },
    'hud.hint': {
        'sk': 'Malý panel v rohu obrazovky: tep, krivka za posledné 3 minúty, pruh záťaže a priebeh relácie. Klik cezeň prejde do hry, do Alt+Tab sa nedostane.',
        'en': 'A small corner panel: heart rate, a 3-minute trend, a load bar and session progress. Clicks pass through to the game and it never shows in Alt+Tab.',
        'ja': 'A small corner panel: heart rate, a 3-minute trend, a load bar and session progress. Clicks pass through to the game and it never shows in Alt+Tab.',
        'zh': 'A small corner panel: heart rate, a 3-minute trend, a load bar and session progress. Clicks pass through to the game and it never shows in Alt+Tab.',
        'ru': 'A small corner panel: heart rate, a 3-minute trend, a load bar and session progress. Clicks pass through to the game and it never shows in Alt+Tab.',
        'es': 'A small corner panel: heart rate, a 3-minute trend, a load bar and session progress. Clicks pass through to the game and it never shows in Alt+Tab.',
        'de': 'A small corner panel: heart rate, a 3-minute trend, a load bar and session progress. Clicks pass through to the game and it never shows in Alt+Tab.',
        'fr': 'A small corner panel: heart rate, a 3-minute trend, a load bar and session progress. Clicks pass through to the game and it never shows in Alt+Tab.',
        'pt': 'A small corner panel: heart rate, a 3-minute trend, a load bar and session progress. Clicks pass through to the game and it never shows in Alt+Tab.',
    },
    'hud.opacity': {
        'sk': 'Priehľadnosť',
        'en': 'Opacity',
        'ja': 'Opacity',
        'zh': 'Opacity',
        'ru': 'Opacity',
        'es': 'Opacity',
        'de': 'Opacity',
        'fr': 'Opacity',
        'pt': 'Opacity',
    },
    'hud.test': {
        'sk': 'Ukázať HUD na 4 s',
        'en': 'Show HUD for 4 s',
        'ja': 'Show HUD for 4 s',
        'zh': 'Show HUD for 4 s',
        'ru': 'Show HUD for 4 s',
        'es': 'Show HUD for 4 s',
        'de': 'Show HUD for 4 s',
        'fr': 'Show HUD for 4 s',
        'pt': 'Show HUD for 4 s',
    },
    'hud.load': {
        'sk': 'ZÁŤAŽ',
        'en': 'LOAD',
        'ja': 'LOAD',
        'zh': 'LOAD',
        'ru': 'LOAD',
        'es': 'LOAD',
        'de': 'LOAD',
        'fr': 'LOAD',
        'pt': 'LOAD',
    },
    'hud.waiting': {
        'sk': 'ČAKÁM NA DÁTA',
        'en': 'WAITING FOR DATA',
        'ja': 'WAITING FOR DATA',
        'zh': 'WAITING FOR DATA',
        'ru': 'WAITING FOR DATA',
        'es': 'WAITING FOR DATA',
        'de': 'WAITING FOR DATA',
        'fr': 'WAITING FOR DATA',
        'pt': 'WAITING FOR DATA',
    },
    'hud.zone.calm': {
        'sk': 'Pokoj',
        'en': 'Calm',
        'ja': 'Calm',
        'zh': 'Calm',
        'ru': 'Calm',
        'es': 'Calm',
        'de': 'Calm',
        'fr': 'Calm',
        'pt': 'Calm',
    },
    'hud.zone.raised': {
        'sk': 'Zvýšená',
        'en': 'Raised',
        'ja': 'Raised',
        'zh': 'Raised',
        'ru': 'Raised',
        'es': 'Raised',
        'de': 'Raised',
        'fr': 'Raised',
        'pt': 'Raised',
    },
    'hud.zone.high': {
        'sk': 'Vysoká',
        'en': 'High',
        'ja': 'High',
        'zh': 'High',
        'ru': 'High',
        'es': 'High',
        'de': 'High',
        'fr': 'High',
        'pt': 'High',
    },
    # The highest zone (heart rate above the player's own high heart rate
    # limit). The displayed name is a calm word without a medical or alarm
    # undertone ("Kriticka" (Critical) sounded like a diagnosis). The
    # internal key stays critical.
    'hud.zone.critical': {
        'sk': 'Špička',
        'en': 'Peak',
        'ja': 'Peak',
        'zh': 'Peak',
        'ru': 'Peak',
        'es': 'Peak',
        'de': 'Peak',
        'fr': 'Peak',
        'pt': 'Peak',
    },
    'hud.session.triggers': {
        'sk': 'PRIPOMIENKY {n}',
        'en': 'CUES {n}',
        'ja': '合図 {n}',
        'zh': '提示 {n}',
        'ru': 'ПОДСКАЗКИ {n}',
        'es': 'AVISOS {n}',
        'de': 'HINWEISE {n}',
        'fr': 'RAPPELS {n}',
        'pt': 'AVISOS {n}',
    },
    'hud.session.over': {
        'sk': 'NAD HRANICOU {time}',
        'en': 'OVER LIMIT {time}',
        'ja': 'OVER LIMIT {time}',
        'zh': 'OVER LIMIT {time}',
        'ru': 'OVER LIMIT {time}',
        'es': 'OVER LIMIT {time}',
        'de': 'OVER LIMIT {time}',
        'fr': 'OVER LIMIT {time}',
        'pt': 'OVER LIMIT {time}',
    },
    'log.monitor_target': {
        'sk': 'Obrázky a panel tepu budem kresliť na: {target}.',
        'en': 'Pictures and the heart-rate panel will now draw on: {target}.',
        'ja': '画像と心拍パネルは次の画面に描きます：{target}。',
        'zh': '图片和心率面板将显示在：{target}。',
        'ru': 'Картинки и панель пульса будут рисоваться на: {target}.',
        'es': 'Las imágenes y el panel de pulso se dibujarán en: {target}.',
        'de': 'Bilder und das Puls-Panel werden jetzt hier gezeichnet: {target}.',
        'fr': 'Les images et le panneau du pouls s’afficheront sur : {target}.',
        'pt': 'As imagens e o painel de pulso serão desenhados em: {target}.',
    },
    'log.exclusive_fullscreen': {
        'sk': 'Okno v popredí zaberá celú obrazovku. Ak je to hra a obrázky v nej nevidíš, beží asi v exkluzívnom fullscreene – Windows v ňom cudzie prekrytia nevykreslí. Prepni ju na „Bez okrajov / Borderless“.',
        'en': 'The window in front fills the whole screen. If it is a game and you cannot see the pictures, it is probably in exclusive fullscreen - Windows draws no overlay on top of that. Switch it to “Borderless”.',
        'ja': '前面のウィンドウが画面全体を占めています。それがゲームで、画像が見えないなら、おそらく排他的フルスクリーンで動いています – その上には、Windows はほかのオーバーレイを描画しません。「ボーダーレス / Borderless」に切り替えてください。',
        'zh': '前台窗口占满了整个屏幕。如果那是游戏，而你在里面看不到图片，它大概是在独占全屏模式下运行——在这种模式下，Windows 不会绘制其他程序的叠加层。请把它切换到“无边框 / Borderless”。',
        'ru': 'Окно на переднем плане занимает весь экран. Если это игра и картинок в ней не видно, она, вероятно, работает в эксклюзивном полноэкранном режиме – Windows не рисует поверх него чужие оверлеи. Переключи её в «Без рамки / Borderless».',
        'es': 'La ventana en primer plano ocupa toda la pantalla. Si es un juego y no ves las imágenes en él, probablemente esté en pantalla completa exclusiva – ahí Windows no dibuja superposiciones ajenas. Cámbialo a «Sin bordes / Borderless».',
        'de': 'Das Fenster im Vordergrund füllt den ganzen Bildschirm. Wenn es ein Spiel ist und du die Bilder darin nicht siehst, läuft es vermutlich im exklusiven Vollbild – darin zeichnet Windows keine fremden Overlays. Stell es auf „Randlos / Borderless“ um.',
        'fr': 'La fenêtre au premier plan occupe tout l’écran. Si c’est un jeu et que tu n’y vois pas les images, il tourne sans doute en plein écran exclusif – Windows n’y dessine pas les superpositions externes. Passe-le en « Sans bordure / Borderless ».',
        'pt': 'A janela em primeiro plano ocupa a tela inteira. Se for um jogo e você não vê as imagens nele, provavelmente está em tela cheia exclusiva – nesse modo o Windows não desenha sobreposições de outros programas. Mude o jogo para “Sem bordas / Borderless”.',
    },
    'log.hr_session_saved': {
        'sk': 'Relácia uložená – priemer {avg} BPM, maximum {max} BPM, špička záťaže {peak}.',
        'en': 'Session saved - average {avg} BPM, peak {max} BPM, load peak {peak}.',
        'ja': 'Session saved - average {avg} BPM, peak {max} BPM, load peak {peak}.',
        'zh': 'Session saved - average {avg} BPM, peak {max} BPM, load peak {peak}.',
        'ru': 'Session saved - average {avg} BPM, peak {max} BPM, load peak {peak}.',
        'es': 'Session saved - average {avg} BPM, peak {max} BPM, load peak {peak}.',
        'de': 'Session saved - average {avg} BPM, peak {max} BPM, load peak {peak}.',
        'fr': 'Session saved - average {avg} BPM, peak {max} BPM, load peak {peak}.',
        'pt': 'Session saved - average {avg} BPM, peak {max} BPM, load peak {peak}.',
    },
    # 0.3: a session from last time that was not saved (crash, Task Manager,
    # power cut) - recovered from the checkpoint
    # (`hr_stats.obnov_rozpracovanu`). The second sentence is honesty: the
    # checkpoint is every 5 minutes. cs/bg in `i18n_cs_bg.py` right by
    # 'log.hr_session_saved'.
    'log.hr_session_recovered': {
        'sk': 'Obnovila som reláciu z {time}, ktorá sa minule neuložila. Posledné minúty v nej môžu chýbať.',
        'en': 'I recovered the session from {time} that didn’t get saved last time. Its last few minutes may be missing.',
        'ja': '前回保存されなかった {time} のセッションを復元しました。最後の数分は欠けているかもしれません。',
        'zh': '我恢复了上次没能保存的 {time} 的记录。最后几分钟可能缺失。',
        'ru': 'Я восстановила сессию от {time}, которая в прошлый раз не сохранилась. Последних минут в ней может не быть.',
        'es': 'Recuperé la sesión del {time}, que la última vez no se guardó. Puede que le falten los últimos minutos.',
        'de': 'Ich habe die Sitzung vom {time} wiederhergestellt, die beim letzten Mal nicht gespeichert wurde. Die letzten Minuten können fehlen.',
        'fr': 'J’ai récupéré la séance du {time}, qui n’avait pas été enregistrée la dernière fois. Ses dernières minutes peuvent manquer.',
        'pt': 'Recuperei a sessão de {time}, que da última vez não foi salva. Os últimos minutos podem estar faltando.',
    },
    # 0.3: dandurf_settings.json could not be read - the broken file is put
    # aside as .corrupt-<time> (`app_prefs.nacitaj_nastavenia`); {name} is
    # only the file name, the path in %APPDATA% carries the account name.
    'log.settings_restored_backup': {
        'sk': 'Nastavenia sa nedali načítať. Pôvodný súbor som odložila ako {name} a obnovila som poslednú zálohu.',
        'en': 'Your settings couldn’t be read. I set the original file aside as {name} and restored the last backup.',
        'ja': '設定を読み込めませんでした。元のファイルを {name} として残し、最後のバックアップから戻しました。',
        'zh': '无法读取设置。我把原文件另存为 {name}，并恢复了最近的备份。',
        'ru': 'Не удалось прочитать настройки. Исходный файл я отложила как {name} и восстановила последнюю резервную копию.',
        'es': 'No se pudo leer la configuración. Guardé aparte el archivo original como {name} y restauré la última copia de seguridad.',
        'de': 'Die Einstellungen ließen sich nicht lesen. Die ursprüngliche Datei habe ich als {name} beiseitegelegt und die letzte Sicherung wiederhergestellt.',
        'fr': 'Impossible de lire les réglages. J’ai mis le fichier d’origine de côté sous le nom {name} et restauré la dernière sauvegarde.',
        'pt': 'Não foi possível ler as configurações. Guardei o arquivo original à parte como {name} e restaurei o último backup.',
    },
    'log.settings_restored_defaults': {
        'sk': 'Nastavenia sa nedali načítať. Pôvodný súbor som odložila ako {name} a začínam s predvolenými.',
        'en': 'Your settings couldn’t be read. I set the original file aside as {name} and I’m starting with the defaults.',
        'ja': '設定を読み込めませんでした。元のファイルを {name} として残し、既定の設定で始めます。',
        'zh': '无法读取设置。我把原文件另存为 {name}，现在从默认设置开始。',
        'ru': 'Не удалось прочитать настройки. Исходный файл я отложила как {name} и начинаю с настроек по умолчанию.',
        'es': 'No se pudo leer la configuración. Guardé aparte el archivo original como {name} y empiezo con los valores predeterminados.',
        'de': 'Die Einstellungen ließen sich nicht lesen. Die ursprüngliche Datei habe ich als {name} beiseitegelegt und beginne mit den Standardwerten.',
        'fr': 'Impossible de lire les réglages. J’ai mis le fichier d’origine de côté sous le nom {name} et je repars des réglages par défaut.',
        'pt': 'Não foi possível ler as configurações. Guardei o arquivo original à parte como {name} e vou começar com os padrões.',
    },
    # 0.3: an installed 0.2 (installer) shares %APPDATA%\Zanshin with the
    # ZIP version and its uninstaller deletes the whole folder on "No".
    # Once, see `app_data._upozorni_na_staru_instalaciu`; {version} from the
    # registry.
    'data.old_installer': {
        'sk': 'Máš ešte nainštalovanú verziu {version}. Keď ju budeš odinštalovať, na otázku o dátach odpovedz Áno — inak zmaže aj históriu tejto verzie.',
        'en': 'You still have version {version} installed. When you uninstall it, answer Yes to the question about your data — otherwise it deletes this version’s history too.',
        'ja': 'バージョン {version} がまだインストールされています。アンインストールするときは、データについての質問に「はい」と答えてください。そうしないと、このバージョンの履歴も削除されます。',
        'zh': '你还装着 {version} 版。卸载它时，在询问数据的问题上请选“是”——否则它也会删除这个版本的历史。',
        'ru': 'У тебя ещё установлена версия {version}. Когда будешь её удалять, на вопрос о данных ответь «Да» — иначе она удалит и историю этой версии.',
        'es': 'Todavía tienes instalada la versión {version}. Cuando la desinstales, responde «Sí» a la pregunta sobre tus datos; si no, borrará también el historial de esta versión.',
        'de': 'Du hast noch Version {version} installiert. Wenn du sie deinstallierst, beantworte die Frage nach deinen Daten mit „Ja“ — sonst löscht sie auch den Verlauf dieser Version.',
        'fr': 'La version {version} est encore installée. Quand tu la désinstalleras, réponds « Oui » à la question sur tes données — sinon elle supprimera aussi l’historique de cette version.',
        'pt': 'Você ainda tem a versão {version} instalada. Quando for desinstalá-la, responda “Sim” à pergunta sobre os seus dados — senão ela apaga também o histórico desta versão.',
    },
})

# --------------------------------------------------------------------------
# REDESIGN: the Today / Cues / In game pages, the breathing bar, the new
# structure of Settings. sk/en by hand, other languages in English for
# now - for later translation.
# --------------------------------------------------------------------------

STRINGS.update({
    'app.version_short': {
        # keep in sync with MyAppVersion in Dandurf.iss (installer)
        #
        # "alfa 0.2", not "2.1": the 2.x numbering was from the days when
        # the app was aimed at Steam as a sequel to its predecessor. It goes
        # to GitHub as what it really is - the first public alpha.
        'sk': 'alfa 0.3.1',
        'en': 'alpha 0.3.1',
        'ja': 'alpha 0.3.1',
        'zh': 'alpha 0.3.1',
        'ru': 'alpha 0.3.1',
        'es': 'alpha 0.3.1',
        'de': 'alpha 0.3.1',
        'fr': 'alpha 0.3.1',
        'pt': 'alpha 0.3.1',
    },
    'nav.dnes': {
        'sk': 'Dnes',
        'en': 'Today',
        'ja': 'Today',
        'zh': 'Today',
        'ru': 'Today',
        'es': 'Today',
        'de': 'Today',
        'fr': 'Today',
        'pt': 'Today',
    },
    'nav.spustace': {
        'sk': 'Pripomienky',
        'en': 'Cues',
        'ja': '合図',
        'zh': '提示',
        'ru': 'Подсказки',
        'es': 'Avisos',
        'de': 'Hinweise',
        'fr': 'Rappels',
        'pt': 'Avisos',
    },
    # It is no longer just "in game": the heart rate sensor moved to the top
    # of this page. Without a watch the widget has nothing to draw, so they
    # belong together.
    'nav.vhre': {
        'sk': 'Hodinky a v hre',
        'en': 'Watch and in-game',
        'ja': '時計とゲーム中',
        'zh': '手表与游戏中',
        'ru': 'Часы и в игре',
        'es': 'Reloj y en el juego',
        'de': 'Uhr und im Spiel',
        'fr': 'Montre et en jeu',
        'pt': 'Relógio e no jogo',
    },
    'nav.vhre_short': {
        'sk': 'V hre',
        'en': 'In-game',
        'ja': 'ゲーム中',
        'zh': '游戏中',
        'ru': 'В игре',
        'es': 'En juego',
        'de': 'Im Spiel',
        'fr': 'En jeu',
        'pt': 'No jogo',
    },
    # NOTE: here were 'kamae.bar_title' ("Hlavný vypínač", Main switch) and
    # 'kamae.bar_sub' ("Klikni ▶ vľavo...", Click ▶ on the left...) - a
    # heading and instructions for the small ▶ icon in the bar. Since 0.3
    # (batch 4) the bar has one button with text (`dock.start`/`dock.stop`)
    # and a quiet sentence `kamae.bar_hint`; the instructions for the icon
    # are no longer needed.
    'session.zanshin.title': {
        'sk': "Kruh sa uzavrel",
        'en': "The circle is complete",
        'ja': "円が閉じた",
        'zh': "圆满了",
        'ru': "Круг замкнулся",
        'es': "El círculo se ha cerrado",
        'de': "Der Kreis hat sich geschlossen",
        'fr': "Le cercle s'est refermé",
        'pt': "O círculo se fechou",
    },
    'session.zanshin.body': {
        'sk': 'Väčšinu posledných večerov pri hre sa ti tep držal blízko tvojho pokoja. Skús ďalší zápas beze mňa. Ak som ti bola plťou cez rieku, na druhom brehu ma netreba niesť ďalej — kráčaj po svojich. A keby som ti niekedy chýbala, breh je vždy tu.',
        'en': "On most of your recent evenings of play, your pulse stayed close to your own calm. Try the next match without me. If I was a raft across the river, you needn't carry me on the far bank — walk on your own. And if you ever need me again, the shore is always here.",
        'ja': '最近のゲームの夜のほとんどで、心拍はあなた自身の平静の近くにとどまっていました。次の試合は、私なしでやってみてください。私が川を渡る筏だったなら、向こう岸でまで背負っていく必要はありません — 自分の足で歩いてください。そしてまた私が必要になったら、岸はいつでもここにあります。',
        'zh': '最近大多数玩游戏的晚上，你的心率都保持在接近你自己平静水平的位置。下一局试试不带我。如果我曾是你渡河的木筏，到了对岸就不必再背着我——用自己的双脚走下去。如果哪天你又需要我，岸一直都在这里。',
        'ru': 'Большинство последних вечеров за игрой твой пульс держался близко к твоему покою. Попробуй следующий матч без меня. Если я была тебе плотом через реку, на том берегу меня не нужно нести дальше — иди своими ногами. А если я когда-нибудь снова тебе понадоблюсь, берег всегда здесь.',
        'es': 'La mayoría de las últimas noches de juego, tu pulso se mantuvo cerca de tu calma. Prueba la próxima partida sin mí. Si fui tu balsa para cruzar el río, en la otra orilla no hace falta seguir cargándome — camina por tu cuenta. Y si algún día me necesitas, la orilla siempre está aquí.',
        'de': 'An den meisten der letzten Abende beim Spielen ist dein Puls nah an deiner Ruhe geblieben. Probier das nächste Match ohne mich. Wenn ich dir ein Floß über den Fluss war, musst du mich am anderen Ufer nicht weitertragen — geh auf eigenen Beinen weiter. Und falls du mich je wieder brauchst: Das Ufer ist immer hier.',
        'fr': 'Pendant la plupart de tes dernières soirées de jeu, ton pouls est resté proche de ton propre calme. Essaie le prochain match sans moi. Si j’ai été pour toi un radeau pour traverser la rivière, sur l’autre rive, inutile de me porter plus loin — marche par toi-même. Et si un jour tu as besoin de moi, la rive est toujours là.',
        'pt': 'Na maioria das suas últimas noites de jogo, o seu pulso ficou perto da sua própria calma. Tente a próxima partida sem mim. Se eu fui a sua jangada para atravessar o rio, na outra margem você não precisa me carregar — siga com as próprias pernas. E se um dia precisar de mim, a margem está sempre aqui.',
    },
    'kamae.running': {
        'sk': 'Sledujem',
        'en': 'Watching',
        'ja': '見守り中',
        'zh': '关注中',
        'ru': 'Наблюдаю',
        'es': 'Observando',
        'de': 'Ich beobachte',
        'fr': 'J’observe',
        'pt': 'Observando',
    },
    'kamae.running_sub': {
        'sk': 'Sledujem tep a čakám na správnu chvíľu.',
        'en': 'Watching your heart rate, waiting for a good moment.',
        'ja': 'Watching your heart rate, waiting for a good moment.',
        'zh': 'Watching your heart rate, waiting for a good moment.',
        'ru': 'Watching your heart rate, waiting for a good moment.',
        'es': 'Watching your heart rate, waiting for a good moment.',
        'de': 'Watching your heart rate, waiting for a good moment.',
        'fr': 'Watching your heart rate, waiting for a good moment.',
        'pt': 'Watching your heart rate, waiting for a good moment.',
    },
    # Four states of the dot in the order `ui_shell._StateDot._redraw`
    # draws them (0.3 batch 4 added the triangle: watching, but heart rate
    # dropped out).
    'sidebar.state_tip': {
        'sk': 'Plná zelená bodka — sledujem. Trojuholník — sledujem, ale tep z hodiniek vypadol. Jantárová bodka v krúžku — „teraz nie“, neozvem sa. Prázdny krúžok — som zastavená; spustíš ma tlačidlom ▶ na stránke Dnes.',
        'en': 'Solid green dot — I’m watching. Triangle — I’m watching, but the heart rate from the watch dropped out. Amber dot in a ring — “not now”, I won’t speak up. Hollow ring — I’m stopped; start me with ▶ on the Today page.',
        'ja': '緑の丸 — 見守り中。三角 — 見守り中ですが、時計からの心拍が途切れました。輪の中のこはく色の点 — 「今はいい」、合図は出しません。中が空の輪 — 停止中。「今日」ページの ▶ で開始できます。',
        'zh': '实心绿点——我在关注。三角形——我在关注，但手表的心率中断了。圆圈里的琥珀色点——“现在不要”，我不会出声。空心圆圈——我已停止；在「今天」页面点 ▶ 即可开始。',
        'ru': 'Сплошная зелёная точка — я наблюдаю. Треугольник — я наблюдаю, но пульс с часов пропал. Янтарная точка в кольце — «не сейчас», я не подам голос. Пустой кружок — я остановлена; запусти меня кнопкой ▶ на странице «Сегодня».',
        'es': 'Punto verde relleno: estoy observando. Triángulo: estoy observando, pero se cortó el pulso del reloj. Punto ámbar en un anillo: «ahora no», no aviso. Círculo vacío: estoy detenida; me inicias con ▶ en la página Hoy.',
        'de': 'Grüner Punkt — ich beobachte. Dreieck — ich beobachte, aber der Puls von der Uhr ist ausgefallen. Bernsteinfarbener Punkt im Ring — „Jetzt nicht“, ich melde mich nicht. Leerer Ring — ich bin gestoppt; starte mich mit ▶ auf der Seite Heute.',
        'fr': 'Point vert plein — j’observe. Triangle — j’observe, mais le pouls de la montre s’est interrompu. Point ambre dans un anneau — « pas maintenant », je ne me manifeste pas. Cercle vide — je suis arrêtée ; lance-moi avec ▶ sur la page Aujourd’hui.',
        'pt': 'Ponto verde cheio — estou observando. Triângulo — estou observando, mas o pulso do relógio caiu. Ponto âmbar num anel — “agora não”, não vou avisar. Círculo vazio — estou parada; você me inicia com ▶ na página Hoje.',
    },
    'kamae.armed': {
        'sk': 'Natiahnuté',
        'en': 'Armed',
        'ja': 'Armed',
        'zh': 'Armed',
        'ru': 'Armed',
        'es': 'Armed',
        'de': 'Armed',
        'fr': 'Armed',
        'pt': 'Armed',
    },
    'kamae.armed_sub': {
        'sk': 'Telo je hore už chvíľu. Počkám, kým sa ti to hodí.',
        'en': 'Your body has been up for a while. I will wait for a good moment.',
        'ja': 'Your body has been up for a while. I will wait for a good moment.',
        'zh': 'Your body has been up for a while. I will wait for a good moment.',
        'ru': 'Your body has been up for a while. I will wait for a good moment.',
        'es': 'Your body has been up for a while. I will wait for a good moment.',
        'de': 'Your body has been up for a while. I will wait for a good moment.',
        'fr': 'Your body has been up for a while. I will wait for a good moment.',
        'pt': 'Your body has been up for a while. I will wait for a good moment.',
    },
    'dnes.lastcue': {
        'sk': 'Naposledy sa ozvala pred {min} min · {label}',
        'en': 'Last spoke {min} min ago · {label}',
        'ja': 'Last spoke {min} min ago · {label}',
        'zh': 'Last spoke {min} min ago · {label}',
        'ru': 'Last spoke {min} min ago · {label}',
        'es': 'Last spoke {min} min ago · {label}',
        'de': 'Last spoke {min} min ago · {label}',
        'fr': 'Last spoke {min} min ago · {label}',
        'pt': 'Last spoke {min} min ago · {label}',
    },
    'dnes.lastcue_now': {
        'sk': 'Práve sa ozvala · {label}',
        'en': 'Just spoke · {label}',
        'ja': 'Just spoke · {label}',
        'zh': 'Just spoke · {label}',
        'ru': 'Just spoke · {label}',
        'es': 'Just spoke · {label}',
        'de': 'Just spoke · {label}',
        'fr': 'Just spoke · {label}',
        'pt': 'Just spoke · {label}',
    },
    'kamae.stopped': {
        'sk': 'Zastavené',
        'en': 'Stopped',
        'ja': 'Stopped',
        'zh': 'Stopped',
        'ru': 'Stopped',
        'es': 'Stopped',
        'de': 'Stopped',
        'fr': 'Stopped',
        'pt': 'Stopped',
    },
    # 0.3: the first start holds back watching until the natural voice is
    # prepared (`app._zacni_sledovat_po_priprave_hlasu`, at most 15 s).
    # No prompt to click - a click would stop the preparation.
    'kamae.voice_prep': {
        'sk': 'Pripravujem hlas',
        'en': 'Preparing the voice',
        'ja': '声を準備しています',
        'zh': '正在准备语音',
        'ru': 'Готовлю голос',
        'es': 'Preparando la voz',
        'de': 'Ich bereite die Stimme vor',
        'fr': 'Je prépare la voix',
        'pt': 'Preparando a voz',
    },
    'kamae.voice_prep_sub': {
        'sk': 'O chvíľu začnem sledovať sama.',
        'en': "I'll start watching by myself in a moment.",
        'ja': 'まもなく自分で見守りを始めます。',
        'zh': '我很快会自己开始留意。',
        'ru': 'Скоро начну отслеживать сама.',
        'es': 'En un momento empiezo a vigilar yo sola.',
        'de': 'Gleich fange ich von selbst an zu beobachten.',
        'fr': 'Je commence à surveiller toute seule dans un instant.',
        'pt': 'Daqui a pouco começo a acompanhar sozinha.',
    },
    # TWO WORDINGS, not one. The app can start by itself when a game starts,
    # but only when automatic profile switching is on - otherwise the
    # sentence would promise something that will not happen.
    # --- the "About" section (Settings -> General, right under Your data) ---
    # It is the author's PERSONAL text, not a description of a feature. That
    # is why it is in his own wording in English too and is not translated
    # into the other languages - a translated personal text is no longer the
    # same text.
    'about.title': {
        'sk': 'O appke',
        'en': 'About',
        'ja': 'About',
        'zh': 'About',
        'ru': 'About',
        'es': 'About',
        'de': 'About',
        'fr': 'About',
        'pt': 'About',
    },
    'about.lead': {
        'sk': 'Ahoj, tu Dandurfin.',
        'en': 'Hey everyone, Dandurfin here.',
        'ja': 'みなさん、こんにちは。Dandurfinです。',
        'zh': '大家好，我是 Dandurfin。',
        'ru': 'Всем привет, это Dandurfin.',
        'es': 'Hola a todos, aquí Dandurfin.',
        'de': 'Hallo zusammen, hier ist Dandurfin.',
        'fr': 'Salut à tous, ici Dandurfin.',
        'pt': 'Olá, pessoal, aqui é o Dandurfin.',
    },
    'about.body': {
        'sk': 'Prečo vlastne Zanshin vznikol? Ako človek, ktorý trávi pri počítači veľkú časť dňa — streamujem a hrám — som si časom všimol vzorec. Pri hraní často skĺzneme do úplného „autopilota“. Buď sa zaberieme tak, že stratíme pojem o čase aj o vlastnom tele, alebo naopak chytíme zbytočný tilt a naštveme sa, keď sa nedarí.\n\nHľadal som spôsob, ako si udržať chladnú hlavu a ostať vo „flow“ aj uprostred akcie alebo v sweaty ranked zápasoch. Vtedy som narazil na pojem zanshin — v bojových umeniach označuje stav plného sústredenia, uvoľnenia a čistej hlavy pripravenej na čokoľvek.\n\nTúto appku som napísal z obyčajnej osobnej potreby. Chcel som nenápadného pomocníka na pozadí, ktorý ma nenechá vyhorieť, občas mi pripomenie zhlboka sa nadýchnuť a udrží ma pri zemi. Nie sú to žiadne komplikované ezoterické cvičenia — ide jednoducho o to, aby nás hry viac bavili, aby sme hrali lepšie a hlavne aby sme sa nenaštvali pre nič za nič.\n\nVyrástol som s hrami ako mnohí z mojej generácie. Za očami sa v nás deje viac, než vidno. Zanshin je môj pokus skúsiť to v mieri: niečo, čo si všimne, nič nechce a nič nepredáva.\n\nA teraz narovinu: nie som programátor ani grafik. Túto appku som napísal vibe codingom — teda spolu s AI, vetu po vete, a učil som sa za pochodu. To, čo som priniesol ja, je nápad a roky strávené pri počítači.\n\nStojím na pleciach obrov. Nič z toho, čo appka robí, som nevymyslel — dýchanie, sústredenie, uvoľnená čeľusť, výskum o tepe a strese aj nástroje, v ktorých je to napísané. Všetko to niekto spravil predo mnou a nechal to voľne dostupné. Preto je Zanshin zadarmo a otvorený pod licenciou GPLv3: ktokoľvek si môže kód pozrieť, upraviť ho a posunúť ďalej — len ho nesmie zavrieť. Kto ho posunie ďalej, musí s ním odovzdať aj zdrojový kód a tú istú licenciu. Zdedil som to takto a chcem to takto aj odovzdať.\n\nAk ti tento prístup sedí, alebo si len chceš zahrať a pokecať, zastav sa u nás:',
        'en': 'Why did Zanshin actually come to be? As someone who spends a huge chunk of the day at the PC, streaming and playing games, I noticed a pattern over time. We often slip into complete “autopilot” mode while gaming. We either get so absorbed that we completely lose track of time and our own bodies, or on the flip side, we catch unnecessary tilt and get frustrated when things go wrong.\n\nI was looking for a way to keep a cool head and stay in the “flow” even in the middle of intense action or sweaty ranked matches. That is when I came across the concept of zanshin — which in martial arts refers to a state of being fully focused, relaxed, and having a clear mind ready for anything.\n\nI coded this app out of a simple personal need. I wanted a subtle background helper that prevents me from burning out, reminds me to take a deep breath every now and then, and keeps me grounded. It is not about any complicated esoteric exercises; it is simply about enjoying our games more, performing better, and most importantly, not getting tilted over nothing.\n\nI grew up with games, like a lot of my generation. More goes on behind the eyes than anyone sees. Zanshin is my attempt to try it in peace: something that notices, wants nothing and sells nothing.\n\nAnd straight up: I am not a programmer or an artist. I vibe coded this app — together with AI, line by line, learning as I went. What I brought to it is the idea and years spent at the PC.\n\nI am standing on the shoulders of giants. Nothing this app does was invented by me — the breathing, the focus, the unclenched jaw, the research on heart rate and stress, the tools it is written in. Someone did all of it before me and left it out in the open. That is why Zanshin is free and open under the GPLv3 licence: anyone can read the code, change it and pass it on — they just cannot close it up. Whoever passes it on has to hand over the source and the same licence with it. I inherited it this way and I want to hand it on the same way.\n\nIf you vibe with this mindset, or if you just want to play some games and hang out, definitely drop by our community:',
        'ja': 'そもそもZanshinはなぜ生まれたのか。一日の大半をパソコンの前で過ごし、配信をしたりゲームをしたりしている僕は、時間が経つうちにあるパターンに気づきました。ゲームをしていると、僕たちはよく完全な「オートパイロット」状態にすべり込んでしまいます。夢中になりすぎて時間も自分の体のことも見失ってしまうか、逆に、うまくいかないと無駄にティルトして苛立ってしまうか、どちらかなんです。\n\n僕は、激しいアクションの最中でも、ピリピリしたランクマッチの中でも、冷静な頭を保って「フロー」の状態でいられる方法を探していました。そんなときに出会ったのが、残心（ざんしん）という考え方です。武道では、完全に集中しながらもリラックスし、何にでも対応できる澄んだ心の状態を指す言葉です。\n\nこのアプリは、ただの個人的な必要から書きました。燃え尽きないように支えてくれて、ときどき深呼吸をするよう思い出させてくれて、地に足をつけさせてくれる——そんな、そっと背後で働いてくれる相棒がほしかったんです。複雑で難解な修行の話ではありません。ただ、ゲームをもっと楽しんで、もっとうまくプレイして、そして何より、何でもないことでティルトしない。それだけのことです。\n\n僕も同じ世代の多くの人と同じように、ゲームと一緒に育ちました。目の奥では、外から見えるよりずっと多くのことが起きています。Zanshinは、それを平和なやり方で試してみようという僕なりの試みです。気づいてくれて、何も求めず、何も売らないもの。\n\nそして正直に言うと、僕はプログラマーでもアーティストでもありません。このアプリは「バイブコーディング」で書きました——つまりAIと一緒に、一文ずつ、走りながら覚えていったんです。僕が持ち込んだのは、アイデアと、パソコンの前で過ごした長い年月だけです。\n\n僕は巨人の肩の上に立っています。このアプリがやっていることで、僕が考え出したものは何ひとつありません——呼吸も、集中も、ゆるめた顎も、心拍とストレスの研究も、これを書くのに使った道具も。すべて誰かが僕より先に作り、そして誰でも使えるように開いたまま残しておいてくれたものです。だからこそZanshinは、GPLv3ライセンスのもとで無料かつオープンです。誰でもコードを読み、書き換え、次へ渡すことができます——ただ、閉じてしまうことだけはできません。次へ渡す人は、ソースコードと同じライセンスも一緒に手渡さなければなりません。僕はこうして受け継ぎ、こうして同じように渡していきたいのです。\n\nこの考え方にピンとくる人も、ただゲームをして一緒にゆるく過ごしたいだけの人も、ぜひ僕たちのコミュニティに立ち寄ってください：',
        'zh': 'Zanshin 到底是怎么诞生的？作为一个每天有很大一部分时间都泡在电脑前、直播和打游戏的人，我慢慢发现了一个规律。玩游戏时，我们常常会完全进入“自动驾驶”模式。要么是太投入，以至于彻底忘了时间，也忘了自己的身体；要么反过来，一不顺就上头，为不该生气的事情生气。\n\n我一直在找一种方法，让自己即便身处激烈的战斗或紧张的排位赛中，也能保持冷静的头脑，留在“心流”里。也正是在那时，我接触到了 zanshin 这个概念——在武术里，它指的是一种全神贯注、放松、头脑清明、随时准备应对一切的状态。\n\n写这个应用，纯粹是出于我自己一个很简单的需求。我想要一个不起眼、在后台默默帮忙的小助手，让我不至于把自己耗空，时不时提醒我深呼吸一下，把我拉回地面。这里没有什么复杂玄乎的练习，说到底就是为了让我们玩游戏更开心、发挥得更好，最重要的是——别为了鸡毛蒜皮的事上头。\n\n我和同龄的很多人一样，是玩着游戏长大的。眼睛背后发生的事，比别人看到的多得多。Zanshin 是我的一次尝试，想用和平的方式去面对：一个会注意到你、什么都不要、什么都不卖的东西。\n\n再说得直白点：我既不是程序员，也不是美术。这个应用是我用 vibe coding 的方式写出来的——和 AI 一起，一行一行地敲，边做边学。我带进来的，就是这个点子，还有多年泡在电脑前的经历。\n\n我是站在巨人的肩膀上。这个应用所做的一切，没有一样是我发明的——呼吸、专注、放松的下颌、关于心率和压力的研究，还有写它所用的那些工具。这一切都是别人在我之前做好、并且免费公开出来的。正因如此，Zanshin 在 GPLv3 许可证下免费且开放：任何人都可以阅读代码、修改它、把它传下去——唯独不能把它封闭起来。谁把它传下去，就必须连同源代码和同一份许可证一起交出去。我是这样继承来的，也想这样传下去。\n\n如果你认同这样的心态，或者只是想一起打打游戏、聊聊天，一定要来我们的社区坐坐：',
        'ru': 'Почему вообще появился Zanshin? Как человек, который проводит за компьютером огромную часть дня — стримлю и играю, — я со временем заметил закономерность. Играя, мы часто скатываемся в полный «автопилот». Либо увлекаемся так, что теряем счёт времени и забываем о собственном теле, либо, наоборот, ловим ненужный тильт и злимся, когда что-то не выходит.\n\nЯ искал способ сохранять холодную голову и оставаться в «потоке» даже посреди жаркого экшена или в потных ранкед-матчах. Тогда я и наткнулся на понятие zanshin — в боевых искусствах оно означает состояние полной сосредоточенности, расслабленности и ясной головы, готовой ко всему.\n\nЭто приложение я написал из простой личной потребности. Мне хотелось незаметного помощника на фоне, который не даст мне выгореть, время от времени напомнит глубоко вдохнуть и удержит меня на земле. Речь не о каких-то сложных эзотерических упражнениях — просто о том, чтобы игры приносили больше удовольствия, чтобы играть лучше и, главное, чтобы не злиться из-за ерунды.\n\nЯ вырос с играми, как многие из моего поколения. За глазами происходит больше, чем кто-либо видит. Zanshin — моя попытка попробовать по-мирному: что-то, что замечает, ничего не требует и ничего не продаёт.\n\nИ честно: я не программист и не художник. Это приложение я написал вайб-кодингом — то есть вместе с ИИ, строчка за строчкой, учась по ходу дела. То, что привнёс я, — это идея и годы, проведённые за компьютером.\n\nЯ стою на плечах гигантов. Ничего из того, что делает это приложение, я не придумал — дыхание, сосредоточенность, расслабленная челюсть, исследования о пульсе и стрессе, да и инструменты, на которых всё это написано. Всё это кто-то сделал до меня и оставил в свободном доступе. Поэтому Zanshin бесплатный и открытый под лицензией GPLv3: любой может посмотреть код, изменить его и передать дальше — только закрыть его нельзя. Кто передаёт его дальше, должен отдать вместе с ним и исходный код, и ту же самую лицензию. Я получил это так и хочу так же передать дальше.\n\nЕсли тебе близок этот настрой или ты просто хочешь поиграть и потусить, обязательно загляни к нам:',
        'es': '¿Por qué surgió Zanshin en realidad? Como alguien que pasa gran parte del día delante del PC —haciendo streaming y jugando— con el tiempo me di cuenta de un patrón. Al jugar caemos a menudo en el «piloto automático» total. O nos metemos tanto que perdemos la noción del tiempo y de nuestro propio cuerpo, o al revés, pillamos un tilt innecesario y nos frustramos cuando las cosas no salen.\n\nBuscaba una forma de mantener la cabeza fría y quedarme en el «flow» incluso en plena acción o en partidas sweaty de ranked. Fue entonces cuando di con el concepto de zanshin — que en las artes marciales designa un estado de concentración plena, relajación y mente clara, lista para cualquier cosa.\n\nProgramé esta app por una simple necesidad personal. Quería un ayudante discreto en segundo plano que no me deje quemarme, que de vez en cuando me recuerde respirar hondo y que me mantenga con los pies en la tierra. No se trata de ningún ejercicio esotérico complicado; se trata simplemente de disfrutar más de los juegos, jugar mejor y, sobre todo, no cabrearnos por nada.\n\nCrecí con los videojuegos, como mucha gente de mi generación. Detrás de los ojos pasa más de lo que nadie ve. Zanshin es mi intento de probarlo en paz: algo que se da cuenta, no pide nada y no vende nada.\n\nY os lo digo sin rodeos: no soy programador ni artista. Esta app la hice a base de vibe coding — junto con la IA, línea a línea, aprendiendo sobre la marcha. Lo que puse yo es la idea y los años pasados delante del PC.\n\nEstoy a hombros de gigantes. Nada de lo que hace esta app lo inventé yo — la respiración, la concentración, la mandíbula relajada, la investigación sobre el ritmo cardíaco y el estrés, las herramientas con las que está escrita. Todo eso ya lo hizo alguien antes que yo y lo dejó a disposición de todos. Por eso Zanshin es gratuito y abierto bajo la licencia GPLv3: cualquiera puede leer el código, modificarlo y pasarlo adelante — lo único que no puede es cerrarlo. Quien lo pase adelante tiene que entregar también el código fuente y la misma licencia. Yo lo heredé así y quiero entregarlo de la misma manera.\n\nSi esta forma de ver las cosas te encaja, o si solo quieres echar unas partidas y pasar el rato, pásate sin falta por nuestra comunidad:',
        'de': 'Warum ist Zanshin eigentlich entstanden? Als jemand, der einen großen Teil des Tages am PC verbringt — ich streame und zocke — ist mir mit der Zeit ein Muster aufgefallen. Beim Spielen rutschen wir oft in den kompletten „Autopilot“. Entweder vertiefen wir uns so sehr, dass wir das Zeitgefühl und den eigenen Körper völlig verlieren, oder wir fangen uns umgekehrt unnötigen Tilt ein und ärgern uns, wenn es nicht läuft.\n\nIch habe nach einem Weg gesucht, einen kühlen Kopf zu bewahren und selbst mitten in der Action oder in sweaty Ranked-Matches im „Flow“ zu bleiben. Damals bin ich auf den Begriff Zanshin gestoßen — in den Kampfkünsten bezeichnet er einen Zustand voller Konzentration, Entspannung und eines klaren Kopfes, der auf alles vorbereitet ist.\n\nDiese App habe ich aus einem ganz einfachen persönlichen Bedürfnis geschrieben. Ich wollte einen unaufdringlichen Helfer im Hintergrund, der mich nicht ausbrennen lässt, mich ab und zu ans tiefe Durchatmen erinnert und mich auf dem Boden hält. Es geht um keine komplizierten esoterischen Übungen — es geht einfach darum, dass uns die Spiele mehr Spaß machen, dass wir besser spielen und vor allem, dass wir uns nicht wegen Kleinigkeiten aufregen.\n\nIch bin mit Games aufgewachsen, wie viele aus meiner Generation. Hinter den Augen passiert mehr, als irgendwer sieht. Zanshin ist mein Versuch, es im Frieden zu probieren: etwas, das hinschaut, nichts will und nichts verkauft.\n\nUnd ganz ehrlich: Ich bin weder Programmierer noch Grafiker. Diese App habe ich per Vibe Coding geschrieben — also zusammen mit KI, Satz für Satz, und ich habe im Laufen dazugelernt. Was ich beigetragen habe, ist die Idee und die Jahre, die ich am PC verbracht habe.\n\nIch stehe auf den Schultern von Riesen. Nichts von dem, was die App tut, habe ich erfunden — das Atmen, die Konzentration, der gelöste Kiefer, die Forschung zu Puls und Stress und auch die Werkzeuge, in denen das Ganze geschrieben ist. Das alles hat jemand vor mir gemacht und frei zugänglich gelassen. Deshalb ist Zanshin kostenlos und offen unter der GPLv3-Lizenz: Jeder kann sich den Code ansehen, ihn ändern und weitergeben — nur zumachen darf er ihn nicht. Wer ihn weitergibt, muss den Quellcode und dieselbe Lizenz mitliefern. Ich habe es so geerbt und ich will es genauso weitergeben.\n\nWenn dir diese Einstellung zusagt, oder wenn du einfach zocken und quatschen willst, schau unbedingt bei uns vorbei:',
        'fr': "Pourquoi Zanshin a-t-il vu le jour, au juste ? En tant que personne qui passe une grande partie de sa journée devant le PC — à streamer et à jouer — j'ai fini par remarquer un schéma qui revient. En jouant, on bascule souvent en mode « pilote automatique » total. Soit on est tellement absorbé qu'on perd complètement la notion du temps et de son propre corps, soit, à l'inverse, on attrape un tilt inutile et on s'agace dès que ça ne va pas.\n\nJe cherchais un moyen de garder la tête froide et de rester dans le « flow » même en pleine action ou dans des parties classées bien sweaty. C'est là que je suis tombé sur le concept de zanshin — qui, dans les arts martiaux, désigne un état de concentration totale, de détente et d'esprit clair, prêt à tout.\n\nJ'ai codé cette appli par simple besoin personnel. Je voulais un assistant discret, en arrière-plan, qui m'empêche de m'épuiser, qui me rappelle de respirer profondément de temps en temps et qui me garde les pieds sur terre. Rien à voir avec des exercices ésotériques compliqués — il s'agit simplement de prendre plus de plaisir à jouer, de mieux jouer et, surtout, de ne pas s'énerver pour un rien.\n\nJ'ai grandi avec les jeux vidéo, comme beaucoup de ma génération. Derrière les yeux, il se passe plus de choses que ce que l'on voit. Zanshin, c'est ma tentative d'essayer en paix : quelque chose qui remarque, ne demande rien et ne vend rien.\n\nEt soyons clairs : je ne suis ni programmeur ni graphiste. J'ai codé cette appli en vibe coding — avec l'IA, ligne par ligne, en apprenant au fur et à mesure. Ce que j'y ai apporté, moi, c'est l'idée et les années passées devant le PC.\n\nJe me tiens sur les épaules de géants. Rien de ce que fait cette appli n'a été inventé par moi — la respiration, la concentration, la mâchoire détendue, les recherches sur le rythme cardiaque et le stress, les outils dans lesquels elle est écrite. Quelqu'un a fait tout ça avant moi et l'a laissé en libre accès. C'est pour ça que Zanshin est gratuit et ouvert sous la licence GPLv3 : n'importe qui peut lire le code, le modifier et le transmettre — il ne peut simplement pas le refermer. Celui qui le transmet doit remettre avec lui le code source et cette même licence. J'en ai hérité ainsi, et je veux le transmettre de la même façon.\n\nSi cet état d'esprit te parle, ou si tu veux juste jouer et passer un bon moment, passe faire un tour dans notre communauté :",
        'pt': 'Por que, afinal, o Zanshin surgiu? Como alguém que passa boa parte do dia no PC — fazendo stream e jogando —, com o tempo percebi um padrão. Jogando, muitas vezes entramos no modo “piloto automático” total. Ou ficamos tão absorvidos que perdemos completamente a noção do tempo e do próprio corpo, ou, ao contrário, entramos num tilt desnecessário e ficamos frustrados quando as coisas dão errado.\n\nEu estava procurando um jeito de manter a cabeça fria e ficar no “flow” mesmo no meio da ação intensa ou de partidas sweaty de ranked. Foi aí que dei de cara com o conceito de zanshin — que, nas artes marciais, designa um estado de concentração total, descontração e mente limpa, pronta para tudo.\n\nEscrevi este app por uma simples necessidade pessoal. Eu queria um ajudante discreto em segundo plano que não me deixasse esgotar, que de vez em quando me lembrasse de respirar fundo e que me mantivesse com os pés no chão. Não são exercícios esotéricos complicados — é simplesmente para a gente se divertir mais com os jogos, jogar melhor e, acima de tudo, não entrar em tilt à toa.\n\nCresci com os jogos, como muita gente da minha geração. Por trás dos olhos acontece mais do que se vê. O Zanshin é a minha tentativa de tentar isso em paz: algo que percebe, não quer nada e não vende nada.\n\nE agora sem rodeios: não sou programador nem artista. Fiz este app com vibe coding — ou seja, junto com a IA, linha por linha, aprendendo pelo caminho. O que eu trouxe foi a ideia e os anos passados no PC.\n\nEstou apoiado nos ombros de gigantes. Nada do que este app faz foi inventado por mim — a respiração, a concentração, a mandíbula solta, a pesquisa sobre frequência cardíaca e estresse, e as ferramentas em que ele foi escrito. Alguém fez tudo isso antes de mim e deixou livremente disponível. É por isso que o Zanshin é gratuito e aberto sob a licença GPLv3: qualquer pessoa pode ver o código, alterá-lo e passá-lo adiante — só não pode fechá-lo. Quem o passa adiante tem de entregar junto também o código-fonte e a mesma licença. Eu o herdei assim e assim quero passá-lo adiante.\n\nSe essa atitude tem a ver com você, ou se você só quer jogar um pouco e bater papo, passe com certeza na nossa comunidade:',
    },
    'about.between_lines': {
        'sk': 'Pre toho, kto číta medzi riadkami:\n\nTáto appka nemeria stres. Meria medzeru — medzi tým, čo hovorí tvoj tep, a tým, čo naozaj cítiš. Číslo je povrch; ty si hĺbka.\n\nA keď sa naučíš počúvať tú medzeru v sebe, začneš ju počuť aj inde — v tom, čo ľudia píšu a čo myslia, čo si žiadajú a čo potrebujú.\n\nNič sa nestráca. Len sa to premieňa — aj pozornosť. Drž dlaň otvorenú.',
        'en': 'For the one who reads between the lines:\n\nThis app does not measure stress. It measures the gap — between what your heart rate says and what you truly feel. The number is the surface; you are the depth.\n\nAnd once you learn to hear that gap in yourself, you will start to hear it elsewhere too — in what people write and what they mean, in what they ask for and what they need.\n\nNothing is lost. It only transforms — attention too. Keep your palm open.',
    },
    # 0.2: the source code is not in the installer (only the compiled
    # build) - so the sentence "the source code comes with it" was not
    # true. The official source and the marking of modified versions per
    # LICENSE-DESIGN.md (GPLv3 7c/7e).
    'about.copyright': {
        'sk': '© 2026 Dandurfin · GNU GPLv3 · Zanshin {version}\nTento program je slobodný softvér. Jeho zdrojový kód je voľne dostupný na github.com/Dandurfin/Zanshin — používať, študovať, upravovať a šíriť ho smie ktokoľvek pod tou istou licenciou. Oficiálny Zanshin je len odtiaľ; kópia odinakiaľ nie je od autora. Ikona a obrázok dojo sú autorove (LICENSE-DESIGN.md). Bez záruky.',
        'en': "© 2026 Dandurfin · GNU GPLv3 · Zanshin {version}\nThis program is free software. Its source code is freely available at github.com/Dandurfin/Zanshin — anyone may use, study, modify and share it under the same licence. The official Zanshin comes only from there; a copy from anywhere else is not from the author. The icon and the dojo picture are the author's own (LICENSE-DESIGN.md). With no warranty.",
        'ja': '© 2026 Dandurfin · GNU GPLv3 · Zanshin {version}\nこのプログラムはフリーソフトウェアです。ソースコードは github.com/Dandurfin/Zanshin で自由に入手でき、同じライセンスのもとで誰でも使用、研究、改変、共有できます。公式の Zanshin はそこから入手できるものだけで、ほかの場所からのコピーは作者によるものではありません。アイコンと道場の画像は作者自身のものです（LICENSE-DESIGN.md）。無保証です。',
        'zh': '© 2026 Dandurfin · GNU GPLv3 · Zanshin {version}\n本程序是自由软件。它的源代码可在 github.com/Dandurfin/Zanshin 自由获取——任何人都可以在同一许可证下使用、研究、修改和分发它。官方的 Zanshin 只来自那里；从其他地方得到的副本并非出自作者。图标和道场图片是作者本人的作品（LICENSE-DESIGN.md）。不提供任何担保。',
        'ru': '© 2026 Dandurfin · GNU GPLv3 · Zanshin {version}\nЭта программа — свободное ПО. Её исходный код свободно доступен на github.com/Dandurfin/Zanshin — использовать, изучать, изменять и распространять её может кто угодно под той же лицензией. Официальный Zanshin — только оттуда; копия из другого места — не от автора. Иконка и изображение додзё принадлежат автору (LICENSE-DESIGN.md). Без каких-либо гарантий.',
        'es': '© 2026 Dandurfin · GNU GPLv3 · Zanshin {version}\nEste programa es software libre. Su código fuente está disponible libremente en github.com/Dandurfin/Zanshin — cualquiera puede usarlo, estudiarlo, modificarlo y distribuirlo bajo la misma licencia. El Zanshin oficial solo viene de ahí; una copia de cualquier otro sitio no es del autor. El icono y la imagen del dojo son del autor (LICENSE-DESIGN.md). Sin garantía.',
        'de': '© 2026 Dandurfin · GNU GPLv3 · Zanshin {version}\nDieses Programm ist freie Software. Sein Quellcode ist frei verfügbar auf github.com/Dandurfin/Zanshin — jeder darf ihn unter derselben Lizenz nutzen, studieren, ändern und weitergeben. Das offizielle Zanshin gibt es nur dort; eine Kopie von anderswo stammt nicht vom Autor. Das Icon und das Dojo-Bild gehören dem Autor (LICENSE-DESIGN.md). Ohne Gewährleistung.',
        'fr': '© 2026 Dandurfin · GNU GPLv3 · Zanshin {version}\nCe programme est un logiciel libre. Son code source est librement disponible sur github.com/Dandurfin/Zanshin — tout le monde peut l’utiliser, l’étudier, le modifier et le diffuser sous la même licence. Le Zanshin officiel ne vient que de là ; une copie venant d’ailleurs n’est pas de l’auteur. L’icône et l’image du dojo appartiennent à l’auteur (LICENSE-DESIGN.md). Sans garantie.',
        'pt': '© 2026 Dandurfin · GNU GPLv3 · Zanshin {version}\nEste programa é software livre. O código-fonte está disponível livremente em github.com/Dandurfin/Zanshin — qualquer pessoa pode usá-lo, estudá-lo, modificá-lo e distribuí-lo sob a mesma licença. O Zanshin oficial vem só de lá; uma cópia de outro lugar não é do autor. O ícone e a imagem do dojo são do próprio autor (LICENSE-DESIGN.md). Sem garantia.',
    },
    'kamae.stopped_sub_auto': {
        'sk': 'Neukladám reláciu a neozvem sa. Spusti ma tlačidlom hore, alebo sa spustím sama, keď zapneš {games}.',
        'en': 'Not recording a session or speaking up. Start me with the button above, or I’ll start by myself when you launch {games}.',
        'ja': 'セッションは記録せず、合図も出しません。上のボタンで開始するか、{games} を起動すれば自分で開始します。',
        'zh': '我不保存记录，也不会出声。用上面的按钮启动我，或者当你打开 {games} 时我会自己启动。',
        'ru': 'Не записываю сессию и не подаю знаков. Запусти меня кнопкой сверху — или я запущусь сама, когда ты откроешь {games}.',
        'es': 'No grabo la sesión ni aviso. Iníciame con el botón de arriba o me inicio sola cuando abras {games}.',
        'de': 'Ich zeichne keine Sitzung auf und melde mich nicht. Starte mich mit dem Knopf oben, oder ich starte von selbst, wenn du {games} öffnest.',
        'fr': 'Je n’enregistre pas de séance et je ne me manifeste pas. Lance-moi avec le bouton ci-dessus, ou je me lance toute seule quand tu ouvres {games}.',
        'pt': 'Não gravo a sessão nem aviso. Você me inicia com o botão acima, ou eu começo sozinha quando você abrir {games}.',
    },
    'kamae.stopped_sub': {
        'sk': 'Neukladám reláciu a neozvem sa. Spusti ma tlačidlom hore.',
        'en': 'Not recording a session or speaking up. Start me with the button above.',
        'ja': 'セッションは記録せず、合図も出しません。上のボタンで開始できます。',
        'zh': '我不保存记录，也不会出声。用上面的按钮启动我。',
        'ru': 'Не записываю сессию и не подаю знаков. Запусти меня кнопкой сверху.',
        'es': 'No grabo la sesión ni aviso. Iníciame con el botón de arriba.',
        'de': 'Ich zeichne keine Sitzung auf und melde mich nicht. Starte mich mit dem Knopf oben.',
        'fr': 'Je n’enregistre pas de séance et je ne me manifeste pas. Lance-moi avec le bouton ci-dessus.',
        'pt': 'Não gravo a sessão nem aviso. Você me inicia com o botão acima.',
    },
    # NOTE: here were 'kamae.meta_time', 'kamae.meta_triggers' and
    # 'kamae.meta_bpm' - labels of the three numbers on the right in the
    # breathing bar. The numbers left the bar (see `ui_kit.KamaeBar`), so
    # the keys had nothing left to read and would only be three more
    # strings to translate into all languages.
    'dnes.hr_title': {
        'sk': 'Tep a záťaž',
        'en': 'Heart rate and load',
        'ja': 'Heart rate and load',
        'zh': 'Heart rate and load',
        'ru': 'Heart rate and load',
        'es': 'Heart rate and load',
        'de': 'Heart rate and load',
        'fr': 'Heart rate and load',
        'pt': 'Heart rate and load',
    },
    # heart rate comes via the app's connection on the phone (0.3 batch 4b)
    'dnes.hr_connected': {
        'sk': 'telefón pripojený',
        'en': 'phone connected',
        'ja': 'watch connected',
        'zh': 'watch connected',
        'ru': 'watch connected',
        'es': 'watch connected',
        'de': 'watch connected',
        'fr': 'watch connected',
        'pt': 'watch connected',
    },
    'dnes.hr_waiting': {
        'sk': 'čakám na hodinky',
        'en': 'waiting for watch',
        'ja': 'waiting for watch',
        'zh': 'waiting for watch',
        'ru': 'waiting for watch',
        'es': 'waiting for watch',
        'de': 'waiting for watch',
        'fr': 'waiting for watch',
        'pt': 'waiting for watch',
    },
    'dnes.bpm_unit': {
        'sk': 'úderov za minútu',
        'en': 'beats per minute',
        'ja': 'beats per minute',
        'zh': 'beats per minute',
        'ru': 'beats per minute',
        'es': 'beats per minute',
        'de': 'beats per minute',
        'fr': 'beats per minute',
        'pt': 'beats per minute',
    },
    'overlay.monitor.pick': {
        'sk': 'Obrazovka',
        'en': 'Screen',
        'ja': 'Screen',
        'zh': 'Screen',
        'ru': 'Screen',
        'es': 'Screen',
        'de': 'Screen',
        'fr': 'Screen',
        'pt': 'Screen',
    },
    'overlay.fine_tune': {
        'sk': 'Doladiť veľkosť a polohu obrázkov…',
        'en': 'Fine-tune picture size and position…',
        'ja': '画像のサイズと位置を微調整…',
        'zh': '微调图片的大小和位置…',
        'ru': 'Точнее настроить размер и положение картинок…',
        'es': 'Ajustar tamaño y posición de las imágenes…',
        'de': 'Größe und Position der Bilder feinjustieren…',
        'fr': 'Ajuster la taille et la position des images…',
        'pt': 'Ajustar tamanho e posição das imagens…',
    },
    'settings.look_title': {
        'sk': 'Vzhľad a jazyk',
        'en': 'Look and language',
        'ja': 'Look and language',
        'zh': 'Look and language',
        'ru': 'Look and language',
        'es': 'Look and language',
        'de': 'Look and language',
        'fr': 'Look and language',
        'pt': 'Look and language',
    },
    'settings.language': {
        'sk': 'Jazyk',
        'en': 'Language',
        'ja': 'Language',
        'zh': 'Language',
        'ru': 'Language',
        'es': 'Language',
        'de': 'Language',
        'fr': 'Language',
        'pt': 'Language',
    },
    # Until 0.2.1 this said "The language of the sample cues changes too" -
    # not true. Switching the language does not rewrite the cue texts in
    # existing profiles: the built-in words are taken in the app's language
    # only when a profile is created (`settings_model.default_slots`,
    # English for sk/cs). So the sentence says what really happens.
    'settings.language_sub': {
        'sk': 'Texty pripomienok, ktoré už máš, sa nezmenia.',
        'en': 'Cues you already have keep their wording.',
        'ja': 'すでにある合図の文言は変わりません。',
        'zh': '已有提示的文字不会改变。',
        'ru': 'Уже созданные подсказки сохранят свой текст.',
        'es': 'Los avisos que ya tienes conservan su texto.',
        'de': 'Hinweise, die du schon hast, behalten ihren Wortlaut.',
        'fr': 'Les rappels que tu as déjà gardent leur texte.',
        'pt': 'Os avisos que você já tem continuam com o mesmo texto.',
    },
    'settings.guide_title': {
        'sk': 'Sprievodca',
        'en': 'Guide',
        'ja': 'Guide',
        'zh': 'Guide',
        'ru': 'Guide',
        'es': 'Guide',
        'de': 'Guide',
        'fr': 'Guide',
        'pt': 'Guide',
    },
    'settings.guide_row': {
        'sk': 'Prečo práve čeľusť, ťažisko a dych',
        'en': 'Why jaw, weight and breath',
        'ja': 'Why jaw, weight and breath',
        'zh': 'Why jaw, weight and breath',
        'ru': 'Why jaw, weight and breath',
        'es': 'Why jaw, weight and breath',
        'de': 'Why jaw, weight and breath',
        'fr': 'Why jaw, weight and breath',
        'pt': 'Why jaw, weight and breath',
    },
    'settings.guide_sub': {
        'sk': 'Krátke vysvetlenie ku každej základnej pripomienke — čo sa v tele deje a prečo to môže pomôcť.',
        'en': 'A short note on each built-in cue — what happens in the body and why it may help.',
        'ja': '基本の合図それぞれについての短い説明 — 体で何が起きているか、なぜ役立つかもしれないか。',
        'zh': '对每条基础提示的简短说明——身体里发生了什么，以及为什么可能有帮助。',
        'ru': 'Короткое пояснение к каждой базовой подсказке — что происходит в теле и почему это может помочь.',
        'es': 'Una breve explicación de cada aviso básico — qué pasa en el cuerpo y por qué puede ayudar.',
        'de': 'Eine kurze Erklärung zu jedem Grund-Hinweis — was im Körper passiert und warum es helfen kann.',
        'fr': 'Une courte explication pour chaque rappel de base — ce qui se passe dans le corps et pourquoi ça peut aider.',
        'pt': 'Uma breve explicação de cada aviso básico — o que acontece no corpo e por que pode ajudar.',
    },
    'safety.title': {
        'sk': 'Čo appka voči hre robí a čo nie',
        'en': "What the app does alongside the game, and what it doesn't",
        'ja': 'アプリがゲームに対してすること、しないこと',
        'zh': '应用对游戏做什么、不做什么',
        'ru': 'Что приложение делает рядом с игрой, а что нет',
        'es': 'Qué hace la app respecto al juego y qué no',
        'de': 'Was die App beim Spiel tut und was nicht',
        'fr': 'Ce que l’app fait vis-à-vis du jeu, et ce qu’elle ne fait pas',
        'pt': 'O que o app faz em relação ao jogo e o que não faz',
    },
    'safety.body': {
        'sk': 'Appka kreslí vlastné priehľadné okno a nič viac. Nevstupuje do procesu hry, nehookuje vykresľovanie, nečíta pamäť hry ani obsah obrazovky. Počas hry okno neberie klik ani zameranie (kliky berie len pri ukážke obrázka („Ukázať“), kým ho ťaháš myšou) a nie je v Alt+Tab. Zámerne sa neskrýva pred screenshotmi ani OBS — to robia podvodné prekrytia. Záruku, že ťa anti-cheat nezablokuje, však môže dať len jeho výrobca.',
        'en': "The app draws its own transparent window and nothing more. It never enters the game process, never hooks rendering, never reads game memory or screen contents. During play the window takes no clicks or focus (it only takes clicks during a picture preview (“Show”), while you drag it with the mouse) and stays out of Alt+Tab. It deliberately does not hide from screenshots or OBS - that is what cheating overlays do. Only the maker of an anti-cheat can guarantee it won't flag you, though.",
        'ja': 'アプリは自分専用の透明なウィンドウを描くだけです。ゲームのプロセスに入り込むことも、描画をフックすることも、ゲームのメモリや画面の内容を読むこともありません。プレイ中、このウィンドウはクリックもフォーカスも受け取らず（クリックを受け取るのは、画像のプレビュー中（「表示」）にマウスでドラッグしているときだけ）、Alt+Tab にも出てきません。スクリーンショットや OBS から意図的に隠れることもしません — それは不正なオーバーレイがすることです。ただし、アンチチートにブロックされないと保証できるのは、そのメーカーだけです。',
        'zh': '应用只绘制自己的透明窗口，仅此而已。它不进入游戏进程，不挂钩（hook）渲染，不读取游戏内存或屏幕内容。游戏过程中，这个窗口不接收点击也不获取焦点（只有在图片预览（“显示”）中、你用鼠标拖动它时才接收点击），也不会出现在 Alt+Tab 中。它刻意不对截图或 OBS 隐藏——那是作弊叠加层才会做的事。不过，能保证反作弊系统不会封禁你的，只有它的开发商。',
        'ru': 'Приложение рисует собственное прозрачное окно — и больше ничего. Оно не входит в процесс игры, не перехватывает рендеринг, не читает память игры и содержимое экрана. Во время игры окно не принимает клики и фокус (клики оно принимает только при показе картинки («Показать»), пока ты перетаскиваешь её мышью) и не появляется в Alt+Tab. Оно намеренно не прячется от скриншотов и OBS — так делают читерские оверлеи. Но гарантию, что анти-чит тебя не заблокирует, может дать только его производитель.',
        'es': 'La app dibuja su propia ventana transparente y nada más. No entra en el proceso del juego, no se engancha al renderizado, no lee la memoria del juego ni el contenido de la pantalla. Durante la partida, la ventana no recibe clics ni el foco (solo recibe clics en la vista previa de la imagen («Mostrar»), mientras la arrastras con el ratón) y no aparece en Alt+Tab. A propósito no se oculta de las capturas de pantalla ni de OBS — eso es lo que hacen las superposiciones para hacer trampas. Aun así, la garantía de que el anti-cheat no te bloquee solo puede darla su fabricante.',
        'de': 'Die App zeichnet ihr eigenes transparentes Fenster und sonst nichts. Sie greift nicht in den Spielprozess ein, hookt kein Rendering und liest weder den Speicher des Spiels noch den Bildschirminhalt. Während des Spiels nimmt das Fenster weder Klicks noch Fokus an (Klicks nimmt es nur in der Bildvorschau („Zeigen“), solange du das Bild mit der Maus ziehst) und taucht nicht in Alt+Tab auf. Es versteckt sich absichtlich nicht vor Screenshots oder OBS — das tun betrügerische Overlays. Eine Garantie, dass dich ein Anti-Cheat nicht sperrt, kann aber nur dessen Hersteller geben.',
        'fr': 'L’app dessine sa propre fenêtre transparente, rien de plus. Elle n’entre pas dans le processus du jeu, ne pose aucun hook sur le rendu, ne lit ni la mémoire du jeu ni le contenu de l’écran. Pendant le jeu, la fenêtre ne prend ni les clics ni le focus (elle ne prend les clics que pendant l’aperçu de l’image (« Afficher »), tant que tu la fais glisser à la souris) et n’apparaît pas dans Alt+Tab. Elle ne se cache volontairement ni des captures d’écran ni d’OBS — c’est ce que font les superpositions de triche. Mais seul l’éditeur d’un anti-cheat peut garantir qu’il ne te bloquera pas.',
        'pt': 'O app desenha a própria janela transparente e nada mais. Não entra no processo do jogo, não faz hook na renderização, não lê a memória do jogo nem o conteúdo da tela. Durante o jogo, a janela não recebe cliques nem foco (só recebe cliques na prévia da imagem (“Mostrar”), enquanto você a arrasta com o mouse) e não aparece no Alt+Tab. De propósito, ela não se esconde de screenshots nem do OBS — é isso que fazem os overlays de cheat. Mas a garantia de que o anti-cheat não vai te bloquear só o fabricante dele pode dar.',
    },
    'slot.record_short': {
        'sk': 'Nahrať',
        'en': 'Record',
        'ja': 'Record',
        'zh': 'Record',
        'ru': 'Record',
        'es': 'Record',
        'de': 'Record',
        'fr': 'Record',
        'pt': 'Record',
    },
    'slot.file_short': {
        'sk': 'Súbor',
        'en': 'File',
        'ja': 'File',
        'zh': 'File',
        'ru': 'File',
        'es': 'File',
        'de': 'File',
        'fr': 'File',
        'pt': 'File',
    },
    'common.open': {
        'sk': 'Otvoriť',
        'en': 'Open',
        'ja': 'Open',
        'zh': 'Open',
        'ru': 'Open',
        'es': 'Open',
        'de': 'Open',
        'fr': 'Open',
        'pt': 'Open',
    },
})

# --- bulk selection and removal of triggers ---
STRINGS.update({
    'slots.remove_selected': {
        'sk': 'Odstrániť označené',
        'en': 'Remove selected',
        'ja': 'Remove selected',
        'zh': 'Remove selected',
        'ru': 'Remove selected',
        'es': 'Remove selected',
        'de': 'Remove selected',
        'fr': 'Remove selected',
        'pt': 'Remove selected',
    },
    'slots.clear_selection': {
        'sk': 'Zrušiť výber',
        'en': 'Clear selection',
        'ja': 'Clear selection',
        'zh': 'Clear selection',
        'ru': 'Clear selection',
        'es': 'Clear selection',
        'de': 'Clear selection',
        'fr': 'Clear selection',
        'pt': 'Clear selection',
    },
    'slots.selected_count': {
        'sk': 'Označené: {n}',
        'en': 'Selected: {n}',
        'ja': 'Selected: {n}',
        'zh': 'Selected: {n}',
        'ru': 'Selected: {n}',
        'es': 'Selected: {n}',
        'de': 'Selected: {n}',
        'fr': 'Selected: {n}',
        'pt': 'Selected: {n}',
    },
    'slots.remove_confirm': {
        'sk': 'Odstrániť {n} označených pripomienok?\n\n{list}',
        'en': 'Remove {n} selected cues?\n\n{list}',
        'ja': '選択した {n} 個の合図を削除しますか？\n\n{list}',
        'zh': '删除所选的 {n} 条提示？\n\n{list}',
        'ru': 'Удалить выбранные подсказки ({n})?\n\n{list}',
        'es': '¿Eliminar los {n} avisos seleccionados?\n\n{list}',
        'de': '{n} ausgewählte Hinweise entfernen?\n\n{list}',
        'fr': 'Supprimer les {n} rappels sélectionnés ?\n\n{list}',
        'pt': 'Remover os {n} avisos selecionados?\n\n{list}',
    },
    'log.slots_removed_bulk': {
        'sk': 'Odstránených pripomienok: {n}.',
        'en': 'Removed {n} cues.',
        'ja': '{n} 個の合図を削除しました。',
        'zh': '已删除 {n} 条提示。',
        'ru': 'Удалено подсказок: {n}.',
        'es': 'Se eliminaron {n} avisos.',
        'de': '{n} Hinweise entfernt.',
        'fr': '{n} rappels supprimés.',
        'pt': 'Removidos {n} avisos.',
    },
})

# --- watch pairing guide (WatchPairingDialog) ---
STRINGS.update({
    'hr.pair_button': {
        'sk': 'Ako spárovať hodinky…',
        'en': 'How to pair your watch…',
        'ja': 'How to pair your watch…',
        'zh': 'How to pair your watch…',
        'ru': 'How to pair your watch…',
        'es': 'How to pair your watch…',
        'de': 'How to pair your watch…',
        'fr': 'How to pair your watch…',
        'pt': 'How to pair your watch…',
    },
    'hr.pair_title': {
        'sk': 'Spárovanie hodiniek',
        'en': 'Pairing your watch',
        'ja': 'Pairing your watch',
        'zh': 'Pairing your watch',
        'ru': 'Pairing your watch',
        'es': 'Pairing your watch',
        'de': 'Pairing your watch',
        'fr': 'Pairing your watch',
        'pt': 'Pairing your watch',
    },
    'hr.pair_intro': {
        'sk': 'Tep ti do počítača pošle appka v telefóne. Zanshin sa jej tvári ako OBS — samotné OBS inštalovať nemusíš.',
        'en': 'The app on your phone sends your heart rate to this PC. To it, Zanshin looks like OBS — you don’t need to install OBS itself.',
        'ja': '心拍は電話のアプリから PC に送られます。Zanshin はそのアプリに OBS のふりをします — OBS 自体をインストールする必要はありません。',
        'zh': '心率由手机上的应用发送到这台电脑。Zanshin 在它看来就像 OBS——你不需要安装 OBS 本身。',
        'ru': 'Пульс на компьютер отправит приложение на телефоне. Для него Zanshin выглядит как OBS — сам OBS устанавливать не нужно.',
        'es': 'El pulso te lo manda al PC la app del móvil. Para ella, Zanshin se hace pasar por OBS: no hace falta instalar OBS.',
        'de': 'Den Puls schickt dir die App auf dem Handy an den PC. Für sie sieht Zanshin wie OBS aus — OBS selbst musst du nicht installieren.',
        'fr': 'C’est l’app du téléphone qui envoie ton pouls au PC. Pour elle, Zanshin se fait passer pour OBS — tu n’as pas besoin d’installer OBS.',
        'pt': 'Quem envia o seu pulso para o PC é o app do celular. Para ele, o Zanshin se passa por OBS — você não precisa instalar o OBS.',
    },
    'hr.pair_this_pc': {
        'sk': 'ADRESA A PORT TOHTO POČÍTAČA — prepíš do telefónu',
        # 0.3: en had a doubled backslash before u2019 in the source, so the
        # window showed a literal backslash and 'u2019'. ja..pt are filled in
        # by _tr7 below.
        'en': 'THIS PC’S ADDRESS AND PORT — enter it in the phone app',
    },
    'hr.pair_ip_unknown': {
        'sk': 'IP sa nepodarilo zistiť',
        'en': 'Could not detect IP',
        'ja': 'Could not detect IP',
        'zh': 'Could not detect IP',
        'ru': 'Could not detect IP',
        'es': 'Could not detect IP',
        'de': 'Could not detect IP',
        'fr': 'Could not detect IP',
        'pt': 'Could not detect IP',
    },
    'hr.pair_ip_help': {
        'sk': 'Otvor Príkazový riadok a napíš ipconfig — hľadaj „IPv4 Address“ (býva 192.168.x.x). Telefón aj počítač musia byť na tej istej Wi‑Fi.',
        'en': 'Open Command Prompt and type ipconfig — look for “IPv4 Address” (usually 192.168.x.x). Phone and PC must be on the same Wi‑Fi.',
        'ja': 'Open Command Prompt and type ipconfig — look for “IPv4 Address” (usually 192.168.x.x). Phone and PC must be on the same Wi‑Fi.',
        'zh': 'Open Command Prompt and type ipconfig——look for “IPv4 Address” (usually 192.168.x.x). Phone and PC must be on the same Wi‑Fi.',
        'ru': 'Open Command Prompt and type ipconfig — look for “IPv4 Address” (usually 192.168.x.x). Phone and PC must be on the same Wi‑Fi.',
        'es': 'Open Command Prompt and type ipconfig — look for “IPv4 Address” (usually 192.168.x.x). Phone and PC must be on the same Wi‑Fi.',
        'de': 'Open Command Prompt and type ipconfig — look for “IPv4 Address” (usually 192.168.x.x). Phone and PC must be on the same Wi‑Fi.',
        'fr': 'Open Command Prompt and type ipconfig — look for “IPv4 Address” (usually 192.168.x.x). Phone and PC must be on the same Wi‑Fi.',
        'pt': 'Open Command Prompt and type ipconfig — look for “IPv4 Address” (usually 192.168.x.x). Phone and PC must be on the same Wi‑Fi.',
    },
    'hr.step1_title': {
        'sk': 'Rovnaká Wi‑Fi a povolenie siete',
        'en': 'Same Wi‑Fi and network permission',
    },
    'hr.step2_title': {
        'sk': 'Nainštaluj appku do telefónu',
        'en': 'Install the phone app',
        'ja': 'Install the phone app',
        'zh': 'Install the phone app',
        'ru': 'Install the phone app',
        'es': 'Install the phone app',
        'de': 'Install the phone app',
        'fr': 'Install the phone app',
        'pt': 'Install the phone app',
    },
    'hr.step2_body': {
        'sk': 'Android / Wear OS: „HeartRateOnStream for OBS“ z Google Play (zdarma). iPhone / Apple Watch: „PulseOSC“ z App Store (platená, zatiaľ nevyskúšaná — autor nemá Apple). Heslo, scéna a zdroj (kroky 3–4) platia len pre appku na Androide. Naskenuj kód nižšie a prepoj appku s hodinkami.',
        'en': 'Android / Wear OS: “HeartRateOnStream for OBS” from Google Play (free). iPhone / Apple Watch: “PulseOSC” from the App Store (paid, untested so far — the author has no Apple device). The password, scene and source (steps 3–4) apply to the Android app only. Scan a code below and connect the app to your watch.',
        'ja': 'Android / Wear OS：Google Play の「HeartRateOnStream for OBS」（無料）。iPhone / Apple Watch：App Store の「PulseOSC」（有料、まだ未検証 — 作者は Apple 製品を持っていません）。パスワード、シーン、ソース（ステップ 3–4）は Android だけに関係します。下のコードを読み取り、アプリを時計とつないでください。',
        'zh': 'Android / Wear OS：Google Play 上的“HeartRateOnStream for OBS”（免费）。iPhone / Apple Watch：App Store 上的“PulseOSC”（付费，尚未测试——作者没有苹果设备）。密码、场景和来源（第 3–4 步）只适用于 Android。扫描下面的二维码，把应用和手表连起来。',
        'ru': 'Android / Wear OS: «HeartRateOnStream for OBS» из Google Play (бесплатно). iPhone / Apple Watch: «PulseOSC» из App Store (платное, пока не проверено — у автора нет устройств Apple). Пароль, сцена и источник (шаги 3–4) относятся только к Android. Отсканируй код ниже и свяжи приложение с часами.',
        'es': 'Android / Wear OS: «HeartRateOnStream for OBS» de Google Play (gratis). iPhone / Apple Watch: «PulseOSC» de la App Store (de pago, sin probar todavía: el autor no tiene Apple). La contraseña, la escena y la fuente (pasos 3–4) son solo para Android. Escanea un código de abajo y conecta la app con el reloj.',
        'de': 'Android / Wear OS: „HeartRateOnStream for OBS“ aus Google Play (kostenlos). iPhone / Apple Watch: „PulseOSC“ aus dem App Store (kostenpflichtig, bisher ungetestet — der Autor hat kein Apple-Gerät). Passwort, Szene und Quelle (Schritte 3–4) gelten nur für Android. Scanne unten einen Code und verbinde die App mit deiner Uhr.',
        'fr': 'Android / Wear OS : « HeartRateOnStream for OBS » sur Google Play (gratuit). iPhone / Apple Watch : « PulseOSC » sur l’App Store (payant, pas encore testé — l’auteur n’a pas d’appareil Apple). Le mot de passe, la scène et la source (étapes 3–4) ne concernent qu’Android. Scanne un code ci-dessous et relie l’app à ta montre.',
        'pt': 'Android / Wear OS: “HeartRateOnStream for OBS” na Google Play (grátis). iPhone / Apple Watch: “PulseOSC” na App Store (pago, ainda não testado — o autor não tem Apple). Senha, cena e fonte (passos 3–4) valem só para Android. Escaneie um código abaixo e conecte o app ao relógio.',
    },
    'hr.step3_title': {
        'sk': 'Zadaj adresu a port',
        'en': 'Enter the address and port',
        'ja': 'Enter the address and port',
        'zh': 'Enter the address and port',
        'ru': 'Enter the address and port',
        'es': 'Enter the address and port',
        'de': 'Enter the address and port',
        'fr': 'Enter the address and port',
        'pt': 'Enter the address and port',
    },
    'hr.step4_title': {
        'sk': 'Vyber scénu a zdroj',
        'en': 'Pick the scene and source',
        'ja': 'Pick the scene and source',
        'zh': 'Pick the scene and source',
        'ru': 'Pick the scene and source',
        'es': 'Pick the scene and source',
        'de': 'Pick the scene and source',
        'fr': 'Pick the scene and source',
        'pt': 'Pick the scene and source',
    },
    'hr.step4_body': {
        'sk': 'Keď sa appka na telefóne pripojí, ponúkne scénu „Zanshin“ a textový zdroj „Tep“. Vyber práve tieto dva — cez ne posiela tvoj tep.',
        'en': 'Once the phone app connects, it will offer a scene named “Zanshin“ and a text source named “Tep“. Select exactly those two — that is how your heart rate comes through.',
        'ja': 'Once the phone app connects, it will offer a scene named “Zanshin“ and a text source named “Tep“. Select exactly those two — that is how your heart rate comes through.',
        'zh': 'Once the phone app connects, it will offer a scene named “Zanshin“ and a text source named “Tep“. Select exactly those two——that is how your heart rate comes through.',
        'ru': 'Once the phone app connects, it will offer a scene named “Zanshin“ and a text source named “Tep“. Select exactly those two — that is how your heart rate comes through.',
        'es': 'Once the phone app connects, it will offer a scene named “Zanshin“ and a text source named “Tep“. Select exactly those two — that is how your heart rate comes through.',
        'de': 'Once the phone app connects, it will offer a scene named “Zanshin“ and a text source named “Tep“. Select exactly those two — that is how your heart rate comes through.',
        'fr': 'Once the phone app connects, it will offer a scene named “Zanshin“ and a text source named “Tep“. Select exactly those two — that is how your heart rate comes through.',
        'pt': 'Once the phone app connects, it will offer a scene named “Zanshin“ and a text source named “Tep“. Select exactly those two — that is how your heart rate comes through.',
    },
    'hr.step5_title': {
        'sk': 'Skontroluj stav pod adresou',
        'en': 'Check the status under the address',
    },
    'hr.trouble_title': {
        'sk': 'Hodinky sa pripoja, ale tep nechodí?',
        'en': 'Watch connects but no heart rate?',
        'ja': 'Watch connects but no heart rate?',
        'zh': 'Watch connects but no heart rate?',
        'ru': 'Watch connects but no heart rate?',
        'es': 'Watch connects but no heart rate?',
        'de': 'Watch connects but no heart rate?',
        'fr': 'Watch connects but no heart rate?',
        'pt': 'Watch connects but no heart rate?',
    },
})

# --- "why it works" on the Today page ---
STRINGS.update({
    'dnes.why_line': {
        'sk': 'Telo v hre stuhne skôr, než si to všimneš — Zanshin na to naviaže krátky reset.',
        'en': 'Your body tenses up mid-game before you notice — Zanshin ties a short reset to that.',
        'ja': 'Your body tenses up mid-game before you notice — Zanshin ties a short reset to that.',
        'zh': 'Your body tenses up mid-game before you notice——Zanshin ties a short reset to that.',
        'ru': 'Your body tenses up mid-game before you notice — Zanshin ties a short reset to that.',
        'es': 'Your body tenses up mid-game before you notice — Zanshin ties a short reset to that.',
        'de': 'Your body tenses up mid-game before you notice — Zanshin ties a short reset to that.',
        'fr': 'Your body tenses up mid-game before you notice — Zanshin ties a short reset to that.',
        'pt': 'Your body tenses up mid-game before you notice — Zanshin ties a short reset to that.',
    },
    'dnes.why_link': {
        'sk': 'Čo je za tým →',
        'en': 'What’s behind it →',
        'ja': 'その背景 →',
        'zh': '背后的道理 →',
        'ru': 'Что за этим стоит →',
        'es': 'Qué hay detrás →',
        'de': 'Was dahintersteckt →',
        'fr': 'Ce qu’il y a derrière →',
        'pt': 'O que há por trás →',
    },
})

# --- drag test of visuals, pictogram colour, Guide in the menu ---
STRINGS.update({
    'nav.cmdk_hint': {
        # button in the side panel (Ctrl+K) - it was hard-coded in Slovak
        'sk': 'Hľadať a prepínať',
        'en': 'Search & switch',
        'ja': '検索と切替',
        'zh': '搜索与切换',
        'ru': 'Поиск и переход',
        'es': 'Buscar y cambiar',
        'de': 'Suchen & wechseln',
        'fr': 'Chercher et basculer',
        'pt': 'Buscar e alternar',
    },
    'overlay.test_done': {
        'sk': 'Hotovo',
        'en': 'Done',
        'ja': 'Done',
        'zh': 'Done',
        'ru': 'Done',
        'es': 'Done',
        'de': 'Done',
        'fr': 'Done',
        'pt': 'Done',
    },
    'overlay.drag_hint': {
        'sk': 'Klikni na „Ukázať“ — obrázok sa objaví na obrazovke. Potiahni ho, kam chceš, a ďalším klikom polohu ulož.',
        'en': 'Click “Show” — the picture appears on screen. Drag it where you want and click again to save the position.',
        'ja': '「表示」を押すと画像が画面に出ます。好きな場所へドラッグし、もう一度クリックすると位置が保存されます。',
        'zh': '点击“显示”，图片会出现在屏幕上。把它拖到你想要的位置，再点一次即可保存位置。',
        'ru': 'Нажми «Показать» — картинка появится на экране. Перетащи её куда хочешь и нажми ещё раз, чтобы сохранить положение.',
        'es': 'Pulsa «Mostrar» y la imagen aparece en pantalla. Arrástrala donde quieras y vuelve a pulsar para guardar la posición.',
        'de': 'Klick auf „Zeigen“ — das Bild erscheint auf dem Bildschirm. Zieh es, wohin du willst, und klick noch einmal, um die Position zu speichern.',
        'fr': 'Clique sur « Afficher » — l’image apparaît à l’écran. Fais-la glisser où tu veux et clique à nouveau pour enregistrer la position.',
        'pt': 'Clique em “Mostrar” — a imagem aparece na tela. Arraste-a para onde quiser e clique de novo para salvar a posição.',
    },
    'overlay.color_title': {
        'sk': 'Farba obrázka',
        'en': 'Picture colour',
        'ja': '画像の色',
        'zh': '图片颜色',
        'ru': 'Цвет картинки',
        'es': 'Color de la imagen',
        'de': 'Bildfarbe',
        'fr': 'Couleur de l’image',
        'pt': 'Cor da imagem',
    },
    'colorpick.hex': {
        'sk': 'Hex', 'en': 'Hex', 'ja': 'Hex', 'zh': 'Hex', 'ru': 'Hex',
        'es': 'Hex', 'de': 'Hex', 'fr': 'Hex', 'pt': 'Hex',
    },
    'colorpick.rgb': {
        'sk': 'R {r}   G {g}   B {b}', 'en': 'R {r}   G {g}   B {b}',
        'ja': 'R {r}   G {g}   B {b}', 'zh': 'R {r}   G {g}   B {b}',
        'ru': 'R {r}   G {g}   B {b}', 'es': 'R {r}   G {g}   B {b}',
        'de': 'R {r}   G {g}   B {b}', 'fr': 'R {r}   G {g}   B {b}',
        'pt': 'R {r}   G {g}   B {b}',
    },
    'colorpick.presets': {
        'sk': 'Z palety', 'en': 'From palette', 'ja': 'パレットから',
        'zh': '从调色板', 'ru': 'Из палитры', 'es': 'De la paleta',
        'de': 'Aus der Palette', 'fr': 'De la palette', 'pt': 'Da paleta',
    },
    'colorpick.reset_default': {
        'sk': 'Predvolená', 'en': 'Default', 'ja': '既定', 'zh': '默认',
        'ru': 'По умолчанию', 'es': 'Predeterminado', 'de': 'Standard',
        'fr': 'Par défaut', 'pt': 'Padrão',
    },
    'colorpick.no_pil': {
        'sk': 'Vlastný výber farby tu nie je dostupný (chýba knižnica Pillow).',
        'en': 'The custom colour picker is unavailable (Pillow library missing).',
        'ja': 'カスタムカラーピッカーは利用できません（Pillow ライブラリがありません）。',
        'zh': '自定义拾色器不可用（缺少 Pillow 库）。',
        'ru': 'Свой выбор цвета недоступен (нет библиотеки Pillow).',
        'es': 'El selector de color personalizado no está disponible (falta la biblioteca Pillow).',
        'de': 'Die eigene Farbauswahl ist nicht verfügbar (Pillow-Bibliothek fehlt).',
        'fr': "Le sélecteur de couleur personnalisé est indisponible (bibliothèque Pillow manquante).",
        'pt': 'O seletor de cor personalizado não está disponível (falta a biblioteca Pillow).',
    },
})

# --- reworked onboarding (4 steps with images; from 0.2 a fifth: cue style) ---
STRINGS.update({
    'ob.step1.kicker': {
        'sk': 'KROK 1 z 5',
        'en': 'STEP 1 of 5',
        'ja': 'ステップ 1 / 5',
        'zh': '第 1 步，共 5 步',
        'ru': 'ШАГ 1 из 5',
        'es': 'PASO 1 de 5',
        'de': 'SCHRITT 1 von 5',
        'fr': 'ÉTAPE 1 sur 5',
        'pt': 'PASSO 1 de 5',
    },
    'ob.step1.title': {
        'sk': 'Toto ti appka pripomenie v hre',
        'en': 'This is what the app reminds you of, mid-game',
        'ja': 'This is what the app reminds you of, mid-game',
        'zh': 'This is what the app reminds you of, mid-game',
        'ru': 'This is what the app reminds you of, mid-game',
        'es': 'This is what the app reminds you of, mid-game',
        'de': 'This is what the app reminds you of, mid-game',
        'fr': 'This is what the app reminds you of, mid-game',
        'pt': 'This is what the app reminds you of, mid-game',
    },
    # 0.2: the app does not confirm the effect (the silent arm is only meant
    # to find it out) - "wants to help you", not "trains you".
    'ob.step1.body': {
        'sk': 'Pri clutchi telo stuhne skôr, než si to všimneš — zovretá čeľusť, zadržaný dych, kŕč v ruke. Zanshin netrénuje aim; chce ti pomôcť dohrať s pokojnejšou hlavou, než s akou začínaš.',
        'en': "In a clutch your body tightens before you notice — a clenched jaw, a held breath, a cramped hand. Zanshin doesn't train your aim; it's meant to help you leave the match calmer than you entered it.",
        'ja': 'クラッチの場面では、気づく前に体がこわばります — 食いしばった顎、止めた息、手のこわばり。Zanshin はエイムを鍛えるものではありません。ゲームを始めたときより穏やかな状態で終えられるよう、手助けしたいのです。',
        'zh': '残局关头，身体会在你察觉之前就僵住——咬紧的下颌、屏住的呼吸、抽紧的手。Zanshin 不训练瞄准；它想帮你离开游戏时比进去时更平静。',
        'ru': 'В клатче тело напрягается раньше, чем ты это заметишь, — сжатая челюсть, задержанное дыхание, судорога в руке. Zanshin не тренирует аим; его задача — помочь тебе закончить игру спокойнее, чем ты её начинаешь.',
        'es': 'En un clutch el cuerpo se tensa antes de que lo notes — la mandíbula apretada, la respiración contenida, la mano agarrotada. Zanshin no entrena tu puntería; quiere ayudarte a salir de la partida con más calma que al entrar.',
        'de': 'Im Clutch verspannt sich der Körper, bevor du es merkst — zusammengebissener Kiefer, angehaltener Atem, verkrampfte Hand. Zanshin trainiert nicht dein Zielen; es will dir helfen, das Spiel ruhiger zu verlassen, als du es betreten hast.',
        'fr': 'Dans un clutch, ton corps se crispe avant que tu le remarques — mâchoire serrée, souffle retenu, crampe dans la main. Zanshin n’entraîne pas ta visée ; il veut t’aider à quitter la partie avec plus de calme qu’au début.',
        'pt': 'Num clutch, o corpo trava antes de você perceber — mandíbula cerrada, respiração presa, câimbra na mão. O Zanshin não treina a sua mira; ele quer te ajudar a sair do jogo com mais calma do que no começo.',
    },
    'ob.step1.cap_grounding': {
        'sk': 'Pusti váhu dole',
        'en': 'Drop your weight',
        'ja': '重心を落として',
        'zh': '沉下重心',
        'ru': 'Опусти центр тяжести',
        'es': 'Baja el peso',
        'de': 'Gewicht senken',
        'fr': 'Relâche ton poids',
        'pt': 'Baixa o peso',
    },
    'ob.step1.cap_jaw': {
        'sk': 'Uvoľni čeľusť',
        'en': 'Unclench your jaw',
        'ja': '顎をゆるめて',
        'zh': '松开下巴',
        'ru': 'Разожми челюсть',
        'es': 'Afloja la mandíbula',
        'de': 'Kiefer lockern',
        'fr': 'Desserre la mâchoire',
        'pt': 'Solta o maxilar',
    },
    'ob.step1.cap_breath': {
        'sk': 'Vydýchni',
        'en': 'Breathe out',
        'ja': '吐いて',
        'zh': '呼气',
        'ru': 'Выдохни',
        'es': 'Espira',
        'de': 'Ausatmen',
        'fr': 'Expire',
        'pt': 'Expira',
    },
    'ob.next': {
        'sk': 'Ďalej',
        'en': 'Next',
        'ja': 'Next',
        'zh': 'Next',
        'ru': 'Next',
        'es': 'Next',
        'de': 'Next',
        'fr': 'Next',
        'pt': 'Next',
    },
    'ob.back': {
        'sk': 'Späť',
        'en': 'Back',
        'ja': 'Back',
        'zh': 'Back',
        'ru': 'Back',
        'es': 'Back',
        'de': 'Back',
        'fr': 'Back',
        'pt': 'Back',
    },
    'ob.skip': {
        'sk': 'Preskočiť na hodinky',
        'en': 'Skip to the watch',
        'ja': 'Skip to the watch',
        'zh': 'Skip to the watch',
        'ru': 'Skip to the watch',
        'es': 'Skip to the watch',
        'de': 'Skip to the watch',
        'fr': 'Skip to the watch',
        'pt': 'Skip to the watch',
    },
    'ob.quit.title': {
        'sk': 'Ukončiť Zanshin?',
        'en': 'Quit Zanshin?',
        'ja': 'Zanshin を終了しますか？',
        'zh': '退出 Zanshin？',
        'ru': 'Закрыть Zanshin?',
        'es': '¿Salir de Zanshin?',
        'de': 'Zanshin beenden?',
        'fr': 'Quitter Zanshin ?',
        'pt': 'Sair do Zanshin?',
    },
    'ob.quit.body': {
        'sk': 'Úvod sa ukáže pri ďalšom spustení.',
        'en': 'The intro will show again next time you start the app.',
        'ja': '次に起動したとき、この案内がもう一度表示されます。',
        'zh': '下次启动时会再次显示这个介绍。',
        'ru': 'Вступление появится снова при следующем запуске.',
        'es': 'La introducción volverá a aparecer la próxima vez que abras la app.',
        'de': 'Die Einführung erscheint beim nächsten Start wieder.',
        'fr': 'L’intro s’affichera de nouveau au prochain lancement.',
        'pt': 'A introdução vai aparecer de novo na próxima vez que você abrir o app.',
    },
    'ob.quit.yes': {
        'sk': 'Ukončiť',
        'en': 'Quit',
        'ja': '終了',
        'zh': '退出',
        'ru': 'Выйти',
        'es': 'Salir',
        'de': 'Beenden',
        'fr': 'Quitter',
        'pt': 'Sair',
    },
    'ob.quit.no': {
        'sk': 'Pokračovať',
        'en': 'Continue',
        'ja': '続ける',
        'zh': '继续',
        'ru': 'Продолжить',
        'es': 'Continuar',
        'de': 'Fortsetzen',
        'fr': 'Continuer',
        'pt': 'Continuar',
    },
    'ob.step2.kicker': {
        'sk': 'KROK 2 z 5',
        'en': 'STEP 2 of 5',
        'ja': 'ステップ 2 / 5',
        'zh': '第 2 步，共 5 步',
        'ru': 'ШАГ 2 из 5',
        'es': 'PASO 2 de 5',
        'de': 'SCHRITT 2 von 5',
        'fr': 'ÉTAPE 2 sur 5',
        'pt': 'PASSO 2 de 5',
    },
    'ob.step2.title': {
        'sk': 'Nenápadné. Mimo stredu obrazovky.',
        'en': 'Unobtrusive. Away from the centre of the screen.',
        'ja': '控えめに。画面の中央を避けて。',
        'zh': '低调。避开屏幕中央。',
        'ru': 'Незаметно. В стороне от центра экрана.',
        'es': 'Discreto. Lejos del centro de la pantalla.',
        'de': 'Unaufdringlich. Weg von der Bildschirmmitte.',
        'fr': 'Discret. Loin du centre de l’écran.',
        'pt': 'Discreto. Longe do centro da tela.',
    },
    'ob.step2.body': {
        'sk': 'Obrázok sa ukáže mimo stredu obrazovky a zase zmizne. Klik cez neho prejde do hry. Presunieš ho na stránke „{page}“ cez „Ukázať“.',
        'en': 'The picture appears away from the centre of the screen and fades again. Clicks go through it to the game. You move it on the “{page}” page with “Show”.',
        'ja': '画像は画面の中央を避けて現れ、また消えます。クリックは画像を通り抜けてゲームに届きます。位置は「ゲーム中」ページの「表示」で動かせます。',
        'zh': '图片会出现在避开屏幕中央的位置，然后再消失。点击会穿过它直达游戏。可以在“游戏中”页面用“显示”来移动它。',
        'ru': 'Картинка появляется в стороне от центра экрана и снова исчезает. Клики проходят сквозь неё в игру. Переместить её можно на странице «В игре» кнопкой «Показать».',
        'es': 'La imagen aparece lejos del centro de la pantalla y vuelve a desaparecer. Los clics la atraviesan y llegan al juego. La mueves en la página «En juego» con «Mostrar».',
        'de': 'Das Bild erscheint abseits der Bildschirmmitte und verschwindet wieder. Klicks gehen durch es hindurch ins Spiel. Verschieben kannst du es auf der Seite „Im Spiel“ mit „Zeigen“.',
        'fr': 'L’image apparaît loin du centre de l’écran, puis disparaît. Les clics la traversent jusqu’au jeu. Tu la déplaces sur la page « En jeu » avec « Afficher ».',
        'pt': 'A imagem aparece longe do centro da tela e some de novo. Os cliques passam por ela até o jogo. Você a move na página “No jogo” com “Mostrar”.',
    },
    'ob.step2.tag_safe': {
        'sk': 'Navrhnuté tak, aby sa hry nedotklo — nič neinjektuje, nič nečíta z hry',
        'en': 'Built to stay out of the game — injects nothing, reads nothing from the game',
        'ja': 'ゲームに触れないよう設計 — 何も注入せず、ゲームから何も読み取らない',
        'zh': '设计上不碰游戏——不注入任何东西，不从游戏读取任何内容',
        'ru': 'Задумано так, чтобы не трогать игру — ничего не внедряет, ничего не читает из игры',
        'es': 'Diseñado para no tocar el juego — no inyecta nada, no lee nada del juego',
        'de': 'So gebaut, dass es das Spiel nicht berührt — injiziert nichts, liest nichts aus dem Spiel',
        'fr': 'Conçu pour ne pas toucher au jeu — n’injecte rien, ne lit rien du jeu',
        'pt': 'Feito para não tocar no jogo — não injeta nada, não lê nada do jogo',
    },
    'ob.step3.kicker': {
        'sk': 'KROK 3 z 5',
        'en': 'STEP 3 of 5',
        'ja': 'ステップ 3 / 5',
        'zh': '第 3 步，共 5 步',
        'ru': 'ШАГ 3 из 5',
        'es': 'PASO 3 de 5',
        'de': 'SCHRITT 3 von 5',
        'fr': 'ÉTAPE 3 sur 5',
        'pt': 'PASSO 3 de 5',
    },
    'ob.step3.title': {
        'sk': 'Bez hodiniek sa appka neozve',
        'en': 'Without a watch the app stays silent',
        'ja': '時計がないとアプリは話しません',
        'zh': '没有手表，应用不会出声',
        'ru': 'Без часов приложение молчит',
        'es': 'Sin reloj la app no habla',
        'de': 'Ohne Uhr bleibt die App stumm',
        'fr': "Sans montre, l'app reste muette",
        'pt': 'Sem relógio o app não fala',
    },
    'ob.step3.body': {
        'sk': 'Kedy sa ozvať, rozhoduje tvoj tep. Bez neho appka nevie, že ti záťaž drží hore, a mlčí.',
        'en': 'Your heart rate decides when to speak up. Without it the app can’t tell your load is up, and stays silent.',
        'ja': 'いつ合図を出すかは、あなたの心拍が決めます。心拍がなければ、アプリは負荷が高いままだとわからず、黙っています。',
        'zh': '什么时候提醒你，由你的心率决定。没有心率，应用就不知道你的负荷一直偏高，只会保持安静。',
        'ru': 'Когда подать знак, решает твой пульс. Без него приложение не знает, что нагрузка держится высокой, и молчит.',
        'es': 'Cuándo avisar lo decide tu pulso. Sin él, la app no sabe que tu carga sigue alta y se queda callada.',
        'de': 'Wann sich die App meldet, entscheidet dein Puls. Ohne ihn weiß sie nicht, dass deine Last oben bleibt, und schweigt.',
        'fr': 'C’est ton pouls qui décide quand se manifester. Sans lui, l’app ne sait pas que ta charge reste haute, et se tait.',
        'pt': 'Quem decide quando avisar é o seu pulso. Sem ele, o app não sabe que a sua carga continua alta e fica calado.',
    },
    'ob.step3.pair_now': {
        'sk': 'Spárovať hodinky teraz',
        'en': 'Pair a watch now',
        'ja': 'Pair a watch now',
        'zh': 'Pair a watch now',
        'ru': 'Pair a watch now',
        'es': 'Pair a watch now',
        'de': 'Pair a watch now',
        'fr': 'Pair a watch now',
        'pt': 'Pair a watch now',
    },
    'ob.step3.pair_queued': {
        'sk': 'Párovanie otvorím po úvode',
        'en': "I'll open pairing after the intro",
        'ja': '案内のあとで時計のつなぎ方を開きます',
        'zh': '介绍结束后，我会打开手表连接',
        'ru': 'Открою подключение часов после вступления',
        'es': 'Abriré la vinculación al terminar la introducción',
        'de': 'Ich öffne das Verbinden nach der Einführung',
        'fr': 'J’ouvrirai la connexion après l’intro',
        'pt': 'Abro o pareamento depois da introdução',
    },
    'ob.step3.later_note': {
        'sk': 'Nechceš teraz? Klikni Ďalej — spárovať môžeš kedykoľvek cez „V hre → Ako spárovať hodinky…“.',
        'en': 'Later? Just hit Next — you can pair any time under “In-game → How to pair your watch…”.',
        'ja': '今はやめておく？「次へ」を押して — 「ゲーム中 → 時計のつなぎ方…」からいつでもつなげます。',
        'zh': '现在不想？点“下一步”——随时可以在“游戏中 → 如何连接手表…”里连接。',
        'ru': 'Не сейчас? Нажми «Далее» — подключить часы можно в любой момент через «В игре → Как подключить часы…».',
        'es': '¿Más tarde? Pulsa Siguiente: puedes vincularlo cuando quieras en «En juego → Cómo vincular tu reloj…».',
        'de': 'Später? Klick einfach auf Weiter — verbinden kannst du jederzeit unter „Im Spiel → Uhr verbinden…“.',
        'fr': 'Plus tard ? Clique sur Suivant — tu peux connecter ta montre à tout moment via « En jeu → Comment connecter ta montre… ».',
        'pt': 'Depois? Clique em Próximo — você pode parear a qualquer momento em “No jogo → Como parear o seu relógio…”.',
    },
    'ob.step4.kicker': {
        'sk': 'KROK 4 z 5',
        'en': 'STEP 4 of 5',
        'ja': 'ステップ 4 / 5',
        'zh': '第 4 步，共 5 步',
        'ru': 'ШАГ 4 из 5',
        'es': 'PASO 4 de 5',
        'de': 'SCHRITT 4 von 5',
        'fr': 'ÉTAPE 4 sur 5',
        'pt': 'PASSO 4 de 5',
    },
})

# --- guided tour (app tour) ---
STRINGS.update({
    'tour.step_of': {
        'sk': 'KROK {n} z {total}',
        'en': 'STEP {n} of {total}',
        'ja': 'STEP {n} of {total}',
        'zh': 'STEP {n} of {total}',
        'ru': 'STEP {n} of {total}',
        'es': 'STEP {n} of {total}',
        'de': 'STEP {n} of {total}',
        'fr': 'STEP {n} of {total}',
        'pt': 'STEP {n} of {total}',
    },
    'tour.next': {
        'sk': 'Ďalej',
        'en': 'Next',
        'ja': 'Next',
        'zh': 'Next',
        'ru': 'Next',
        'es': 'Next',
        'de': 'Next',
        'fr': 'Next',
        'pt': 'Next',
    },
    'tour.skip': {
        'sk': 'Preskočiť',
        'en': 'Skip',
        'ja': 'Skip',
        'zh': 'Skip',
        'ru': 'Skip',
        'es': 'Skip',
        'de': 'Skip',
        'fr': 'Skip',
        'pt': 'Skip',
    },
    'tour.done_btn': {
        'sk': 'Rozumiem',
        'en': 'Got it',
        'ja': 'Got it',
        'zh': 'Got it',
        'ru': 'Got it',
        'es': 'Got it',
        'de': 'Got it',
        'fr': 'Got it',
        'pt': 'Got it',
    },
    'tour.welcome.title': {
        'sk': 'Rýchla prehliadka',
        'en': 'Quick tour',
        'ja': 'Quick tour',
        'zh': 'Quick tour',
        'ru': 'Quick tour',
        'es': 'Quick tour',
        'de': 'Quick tour',
        'fr': 'Quick tour',
        'pt': 'Quick tour',
    },
    'tour.welcome.body': {
        'sk': 'Ukážem ti päť miest v appke — asi minúta. Preskočiť môžeš kedykoľvek.',
        'en': "I'll show you five places in the app — about a minute. You can skip any time.",
        'ja': "I'll show you five places in the app — about a minute. You can skip any time.",
        'zh': "I'll show you five places in the app——about a minute. You can skip any time.",
        'ru': "I'll show you five places in the app — about a minute. You can skip any time.",
        'es': "I'll show you five places in the app — about a minute. You can skip any time.",
        'de': "I'll show you five places in the app — about a minute. You can skip any time.",
        'fr': "I'll show you five places in the app — about a minute. You can skip any time.",
        'pt': "I'll show you five places in the app — about a minute. You can skip any time.",
    },
    'tour.triggers.title': {
        'sk': 'Pripomienky',
        'en': 'Cues',
        'ja': '合図',
        'zh': '提示',
        'ru': 'Подсказки',
        'es': 'Avisos',
        'de': 'Hinweise',
        'fr': 'Rappels',
        'pt': 'Avisos',
    },
    # 0.2 (stress-gate): no longer "at the next break" - the voice comes only
    # in a break when load is not rising, and in the critical zone it stays
    # silent. The other 7 languages are in English for now (same as `_sk_en`,
    # which is not here yet).
    'tour.triggers.body': {
        'sk': 'Tu nastavíš, ČO poviem — slová, hlas a zvuk. KEDY, rozhoduje tvoj tep: keď záťaž chvíľu drží hore, ozvem sa v pauze, v ktorej už nestúpa; v pásme Špička mlčím. Šípka pri každej pripomienke ukáže, prečo práve táto.',
        'en': 'Here you set WHAT I say — the words, the voice and the sound. WHEN is up to your heart rate: when your load holds up for a while, I speak up in a pause in which it is no longer climbing; in the peak zone I stay quiet. The arrow at each cue shows why this one.',
        'ja': 'ここでは、私が「何を」話すか — 言葉、声、音 — を設定します。「いつ」かは心拍が決めます：負荷がしばらく高いまま続いたら、もう上がっていない合間に声をかけます。「ピーク」ゾーンでは黙っています。各合図の矢印を開くと、なぜその合図なのかがわかります。',
        'zh': '在这里设置我说“什么”——话语、声音和音效。“什么时候”由你的心率决定：负荷持续偏高一阵子后，我会在它不再上升的停顿里提醒你；在“高峰”区间我保持安静。每条提示旁的箭头会告诉你为什么是它。',
        'ru': 'Здесь ты задаёшь, ЧТО я скажу — слова, голос и звук. КОГДА — решает твой пульс: если нагрузка какое-то время держится высокой, я подаю знак в паузе, в которой она уже не растёт; в зоне «Пик» я молчу. Стрелка у каждой подсказки покажет, почему именно она.',
        'es': 'Aquí eliges QUÉ digo: las palabras, la voz y el sonido. CUÁNDO lo decide tu pulso: si la carga se mantiene alta un rato, aviso en una pausa en la que ya no sube; en la zona Pico me callo. La flecha de cada aviso te explica por qué ese.',
        'de': 'Hier stellst du ein, WAS ich sage — Worte, Stimme und Ton. WANN, entscheidet dein Puls: Bleibt deine Last eine Weile oben, melde ich mich in einer Pause, in der sie nicht mehr steigt; in der Zone Spitze schweige ich. Der Pfeil bei jedem Hinweis zeigt, warum gerade dieser.',
        'fr': 'Ici, tu règles CE QUE je dis — les mots, la voix et le son. QUAND, c’est ton pouls qui décide : si ta charge reste haute un moment, je me manifeste pendant une pause où elle ne monte plus ; dans la zone Pic, je me tais. La flèche de chaque rappel montre pourquoi celui-ci.',
        'pt': 'Aqui você define O QUE eu digo — as palavras, a voz e o som. QUANDO, quem decide é o seu pulso: se a carga fica alta por um tempo, aviso numa pausa em que ela já não está subindo; na zona Pico fico calada. A seta em cada aviso mostra por que justamente esse.',
    },
    # The step about the mark (the enso in the centre of Today; the key "dock"
    # stayed from the QuickDock days). 0.3: the text claimed a green/red
    # enso, but the code always draws it in the theme's accent colour
    # (`hud_paint.render_enso`) - the state is carried by MOTION: while
    # watching it breathes, stopped it stands still, an armed trigger = an
    # inner ring. A click on the enso really toggles (`_dnes_canvas_click`)
    # and the status dot is at the top of the side panel (`_StateDot`). The
    # text deliberately does not name the colour of the dot. `_sk_en` is not
    # defined yet at this point of the file, hence a full dict; the other
    # languages here are = en and `_tr7` below gives the translation.
    'tour.dock.title': {
        'sk': 'Ensō — stav appky',
        'en': "The ensō — the app's state",
        'ja': "The ensō — the app's state",
        'zh': "The ensō——the app's state",
        'ru': "The ensō — the app's state",
        'es': "The ensō — the app's state",
        'de': "The ensō — the app's state",
        'fr': "The ensō — the app's state",
        'pt': "The ensō — the app's state",
    },
    'tour.dock.body': {
        'sk': 'Toto je ensō, značka appky. Keď sledujem, pomaly dýcha; keď stojím, je nehybné. Pomalý prstenec vnútri znamená, že čakám na vhodnú chvíľu. Klikom ma spustíš alebo zastavíš. Stav ukazuje aj bodka vľavo hore.',
        'en': "This is the ensō, the app's mark. While I'm watching, it slowly breathes; when stopped, it is still. A slow ring inside means I'm waiting for a good moment. Click it to start or stop me. The dot at the top left shows the state too.",
        'ja': "This is the ensō, the app's mark. While I'm watching, it slowly breathes; when stopped, it is still. A slow ring inside means I'm waiting for a good moment. Click it to start or stop me. The dot at the top left shows the state too.",
        'zh': "This is the ensō, the app's mark. While I'm watching, it slowly breathes; when stopped, it is still. A slow ring inside means I'm waiting for a good moment. Click it to start or stop me. The dot at the top left shows the state too.",
        'ru': "This is the ensō, the app's mark. While I'm watching, it slowly breathes; when stopped, it is still. A slow ring inside means I'm waiting for a good moment. Click it to start or stop me. The dot at the top left shows the state too.",
        'es': "This is the ensō, the app's mark. While I'm watching, it slowly breathes; when stopped, it is still. A slow ring inside means I'm waiting for a good moment. Click it to start or stop me. The dot at the top left shows the state too.",
        'de': "This is the ensō, the app's mark. While I'm watching, it slowly breathes; when stopped, it is still. A slow ring inside means I'm waiting for a good moment. Click it to start or stop me. The dot at the top left shows the state too.",
        'fr': "This is the ensō, the app's mark. While I'm watching, it slowly breathes; when stopped, it is still. A slow ring inside means I'm waiting for a good moment. Click it to start or stop me. The dot at the top left shows the state too.",
        'pt': "This is the ensō, the app's mark. While I'm watching, it slowly breathes; when stopped, it is still. A slow ring inside means I'm waiting for a good moment. Click it to start or stop me. The dot at the top left shows the state too.",
    },
    'tour.done.title': {
        'sk': 'To je všetko',
        'en': "That's it",
        'ja': "That's it",
        'zh': "That's it",
        'ru': "That's it",
        'es': "That's it",
        'de': "That's it",
        'fr': "That's it",
        'pt': "That's it",
    },
    'tour.done.body': {
        'sk': 'Prehliadku spustíš znova kedykoľvek v Nastaveniach. Príjemné hranie.',
        'en': 'You can replay this tour any time in Settings. Enjoy your game.',
        'ja': 'You can replay this tour any time in Settings. Enjoy your game.',
        'zh': 'You can replay this tour any time in Settings. Enjoy your game.',
        'ru': 'You can replay this tour any time in Settings. Enjoy your game.',
        'es': 'You can replay this tour any time in Settings. Enjoy your game.',
        'de': 'You can replay this tour any time in Settings. Enjoy your game.',
        'fr': 'You can replay this tour any time in Settings. Enjoy your game.',
        'pt': 'You can replay this tour any time in Settings. Enjoy your game.',
    },
    'tour.done.no_watch': {
        'sk': 'Ešte jedno: bez hodiniek mlčím. Spáruj ich, keď budeš mať chvíľu.',
        'en': 'One more thing: without a watch I stay silent. Pair it when you have a moment.',
        'ja': 'もうひとつ：時計がないと、私は黙ったままです。時間のあるときにつないでください。',
        'zh': '还有一件事：没有手表，我就不出声。有空的时候把它连上吧。',
        'ru': 'И ещё: без часов я молчу. Подключи их, когда будет минутка.',
        'es': 'Una cosa más: sin reloj me quedo callada. Vincúlalo cuando tengas un momento.',
        'de': 'Noch etwas: Ohne Uhr bleibe ich still. Verbinde sie, wenn du kurz Zeit hast.',
        'fr': 'Encore une chose : sans montre, je reste silencieuse. Connecte-la quand tu auras un moment.',
        'pt': 'Mais uma coisa: sem relógio, eu fico em silêncio. Pareie quando tiver um tempinho.',
    },
    'settings.tour_row': {
        'sk': 'Prehliadka appky',
        'en': 'App tour',
        'ja': 'App tour',
        'zh': 'App tour',
        'ru': 'App tour',
        'es': 'App tour',
        'de': 'App tour',
        'fr': 'App tour',
        'pt': 'App tour',
    },
    'settings.tour_sub': {
        'sk': 'Krátka prehliadka, kde čo je.',
        'en': 'A short tour of where things are.',
        'ja': 'A short tour of where things are.',
        'zh': 'A short tour of where things are.',
        'ru': 'A short tour of where things are.',
        'es': 'A short tour of where things are.',
        'de': 'A short tour of where things are.',
        'fr': 'A short tour of where things are.',
        'pt': 'A short tour of where things are.',
    },
    'settings.tour_btn': {
        'sk': 'Spustiť prehliadku',
        'en': 'Start tour',
        'ja': 'Start tour',
        'zh': 'Start tour',
        'ru': 'Start tour',
        'es': 'Start tour',
        'de': 'Start tour',
        'fr': 'Start tour',
        'pt': 'Start tour',
    },
})


def _sk_en(sk, en):
    """sk + en by hand, the other languages in English for now (to be
    translated - list in preklad_TODO.csv). The same convention as
    before, just without eleven lines per key. The translation into ja..pt
    is filled in by `_tr7`, Czech and Bulgarian by the module
    `i18n_cs_bg.py` (end of file)."""
    return {"sk": sk, "en": en, "ja": en, "zh": en, "ru": en, "es": en,
            "de": en, "fr": en, "pt": en, "cs": en, "bg": en}


# --- heart rate session history, metrics from the pulse,
# recommendations, sources on heart rate ---
# The metric texts are the exact wording from the spec (for the player,
# not for a doctor). Nowhere "HRV" as something the app measures; nowhere
# a medical diagnosis.
STRINGS.update({
    'nav.historia': _sk_en('História', 'History'),
    'history.title': _sk_en('História relácií', 'Session history'),
    'history.subtitle': _sk_en(
        'Ukladajú sa sem relácie s aspoň minútou tepu (posledných 400).',
        'Sessions with at least a minute of heart rate are saved here (the last 400).'),
    'history.empty': _sk_en(
        'Zatiaľ žiadna relácia. Spáruj hodinky ({page} → Ako spárovať hodinky…), spusti ma tlačidlom ▶ na stránke Dnes a zahraj si aspoň minútu — po zastavení sa relácia objaví tu.',
        'No sessions yet. Pair your watch ({page} → How to pair your watch…), start me with ▶ on the Today page and play for at least a minute — once you stop, the session shows up here.'),
    'history.insights_title': _sk_en(
        'Čo som si všimla',
        'What I noticed'),
    # B3-worlds: insights are computed only from the world that is currently
    # active - "from the whole history" would no longer be true (old
    # translations deleted).
    'history.insights_note': _sk_en(
        'Počíta sa na pozadí z histórie tohto sveta. Sú to postrehy a tipy, nie diagnózy.',
        "Computed in the background from this world's history. Observations and tips, not diagnoses."),
    'history.analysis_running': _sk_en('Analyzujem históriu…', 'Analysing history…'),
    'history.analysis_stamp': _sk_en('Analýza z {when}', 'Analysis from {when}'),
    'history.recompute': _sk_en('Prepočítať', 'Recompute'),
    'history.trend_title': _sk_en('Vývoj naprieč reláciami', 'Trend across sessions'),
    # {slope} is ready-made text from `i18n.cislo` (decimal comma by
    # language, minus sign U+2212), not the format {slope:+.1f} - that gave
    # "-2.0" in Slovak too (0.3, batch 4).
    'history.trend_delta': _sk_en('{first} → {last} BPM, trend {slope} BPM/týždeň',
                                  '{first} → {last} BPM, trend {slope} BPM/week'),
    'history.trend_need_more': _sk_en(
        'Relácie sú zatiaľ príliš blízko pri sebe na trend — over o pár dní.',
        'Sessions are still too close together for a trend — check back in a few days.'),
    'history.trend_simple_delta': _sk_en('{first} → {last}', '{first} → {last}'),
    'history.empty_period': _sk_en('V tomto období zatiaľ nič.', 'Nothing in this period yet.'),
    'history.period.day': _sk_en('Deň', 'Day'),
    'history.period.week': _sk_en('Týždeň', 'Week'),
    'history.period.month': _sk_en('Mesiac', 'Month'),
    'history.period.year': _sk_en('Rok', 'Year'),

    # NOTE: there were 14 keys 'settings.dojo_*' here - heading, description,
    # the slider's end labels and the live feedback bands
    # ("Vypnuté/Jemné/Stredné/Výrazné/Plné" - Off/Subtle/Medium/Strong/Full -
    # + messages about readability) for the "Dojo background" panel. The
    # panel and the photo strip above the title bar were removed, so nothing
    # called these keys any more - they would only remain as 14 more strings
    # to translate into 7 languages in preklad_TODO.csv.
    'history.sessions_title': _sk_en('Relácie', 'Sessions'),
    'history.col_date': _sk_en('Dátum', 'Date'),
    'history.col_duration': _sk_en('Dĺžka', 'Length'),
    'history.col_avg': _sk_en('Priemer', 'Average'),
    'history.col_minmax': _sk_en('Min / max', 'Min / max'),
    'history.col_over': _sk_en(
        'Nad hranicou',
        'Over HR limit'),
    'history.col_triggers': _sk_en(
        'Pripomienky',
        'Cues'),
    'history.col_peak': _sk_en('Špička záťaže', 'Peak load'),
    'history.col_hrr': _sk_en(
        'Zotavenie',
        'Recovery'),
    'history.col_hrpi': _sk_en(
        'Výdrž',
        'Persist.'),
    'history.info_more': _sk_en('ⓘ čo to znamená', 'ⓘ what it means'),
    'history.info_less': _sk_en('ⓘ skryť', 'ⓘ hide'),
    # "How it came about" (0.2, the author's words) - a panel in History and
    # the end of the "A raft across the river" card in the Guide. It replaced
    # a long list of studies: none of them tests Zanshin or its cues, the
    # full list is in ZDROJE.md. Three examples go under the text
    # (guide_content.PHILOSOPHY_SOURCES). „Postavil som ho“ (I built it) is
    # said by the AUTHOR, not the app - hence the masculine form.
    'origin.title': _sk_en('Ako to vzniklo', 'How it came about'),
    'origin.text': _sk_en(
        'Vyrástol som s hrami ako mnohí z mojej generácie. Za očami sa v nás deje viac, než vidno. Zanshin je môj pokus skúsiť to v mieri: niečo, čo si všimne, nič nechce a nič nepredáva.\n\nZanshin nevymyslel nič nové. Stojí na verejnom výskume o tepe, strese a dýchaní a na nástrojoch, ktoré iní nechali otvorené. Postavil som ho pomocou AI a ladil na vlastných večeroch pri hraní. Je to alfa a stále sa testuje — aj preto sa ťa appka po relácii pýta, či pripomienka sadla, a na začiatku asi každá štvrtá, neskôr každá desiata pripomienka zámerne mlčí, aby sa dalo porovnať, či pripomienky naozaj pomáhajú. Záťaž je priznaná zloženina troch vecí, ktoré sa z tepu naozaj dajú zistiť: o koľko si nad svojím pokojom, ako rýchlo tep stúpa a ako dlho ostáva hore. Hranice si appka po prvých pár večeroch počíta z tvojich vlastných relácií. Nie je to zdravotnícka pomôcka a nikto ju klinicky neoveroval.',
        "I grew up with games, like a lot of my generation. More goes on behind the eyes than anyone sees. Zanshin is my attempt to try it in peace: something that notices, wants nothing and sells nothing.\n\nZanshin didn't invent anything new. It stands on public research into heart rate, stress and breathing, and on tools that others left open. I built it with the help of AI and tuned it over my own evenings of gaming. It's an alpha and still being tested — that's also why the app asks you after a session whether the cue landed, and why at first roughly one cue in four, later one in ten, stays silent on purpose, so it can be compared whether the cues really help. Load is an openly admitted mix of three things that heart rate can really tell: how far you are above your own calm, how fast your pulse is climbing and how long it stays up. After the first few evenings, the app works out its thresholds from your own sessions. It is not a medical device, and nobody has validated it clinically."),
    'origin.examples': _sk_en('Pár príkladov, o ktoré sa opiera:',
                              'A few examples it leans on:'),
    'origin.full_list': _sk_en('Celý zoznam zdrojov je na GitHube v ZDROJE.md.',
                               'The full list of sources is on GitHub in ZDROJE.md.'),

    # --- metrics: a short text (the sentence next to the number) +
    # "what it means" (2-3 sentences) ---
    'metric.bpm.short': _sk_en('Koľko úderov za minútu ti bije srdce práve teraz.',
                               'How many times per minute your heart is beating right now.'),
    'metric.bpm.more': _sk_en(
        'Základná hodnota. Sama o sebe nič nehovorí — dôležité je, ako sa mení oproti tvojmu pokoju a ako rýchlo klesá, keď sa upokojíš.',
        'The base number. On its own it says little — what matters is how it moves against your resting level and how fast it drops when you calm down.'),
    # One-word label of a card on the Today page. The card shows a BIG
    # number and this label under it - `title` would be far too long there
    # and in German, French and Russian it would widen the whole right
    # column at the expense of the centre (measured: by up to 105 px).
    'metric.baseline.tag': _sk_en(
        'pokojový tep',
        'resting HR'),
    'metric.hrr.tag': _sk_en('zotavenie', 'recovery'),
    'metric.over.tag': _sk_en(
        'nad hranicou tepu',
        'over HR limit'),
    'metric.breath.tag': _sk_en(
        'pripomienky',
        'cues'),
    'metric.avg.tag': _sk_en('priemer', 'average'),
    'metric.max.tag': _sk_en('maximum', 'highest'),
    'metric.peak.tag': _sk_en('špička záťaže', 'peak load'),
    'metric.week.tag': _sk_en('týždeň', 'this week'),
    # 0.2 (widgets-history). No card may be wider than "nad hranicou" (over
    # HR limit) with 12:34 (measured: 195 px at 150 %) - otherwise it widens
    # the column at the expense of the centre. That is why "cítené/merané"
    # has no spaces (194, with " · " 200).
    'metric.session_len.tag': _sk_en('relácia', 'session'),
    'metric.last_cue.tag': _sk_en(
        'od pripomienky',
        'since cue'),
    'metric.calm_time.tag': _sk_en('v pokoji', 'in calm'),
    'metric.signal.tag': _sk_en('signál', 'signal'),
    'metric.felt_vs_measured.tag': _sk_en('cítené/merané', 'felt/measured'),
    'metric.baseline.title': _sk_en('Pokojová základňa', 'Resting baseline'),
    'metric.baseline.short': _sk_en(
        'Tvoj tep v pokoji — keď ťa nič nenaháňa.',
        'Your pulse at rest — when nothing is pushing you.'),
    'metric.baseline.more': _sk_en(
        'Počítam si ju z tvojich najpokojnejších chvíľ. Keď stúpa deň za dňom, telo môže byť unavené alebo v strese — nie nutne z hrania (spánok, kofeín, choroba). Preto ju sledujem v čase, nie ako jedno číslo.',
        'I derive it from your calmest moments. When it climbs day after day, your body may be tired or stressed — not necessarily from gaming (sleep, caffeine, illness). That is why I track it over time, not as a single number.'),
    # C2 (0.2): the old sentence "how much the game loads you" promised more
    # than the app can do - the resting level is also taken from previous
    # evenings, so the bar shows coffee or tiredness too, not just the game.
    # Since 0.2 the word above the bar is heart rate against rest
    # (HeartStats.zone), not load, and it does not trigger a cue. Since 0.2
    # (stress-gate) it does, however, stop it in the critical zone - the
    # sentence says so.
    'metric.load.short': _sk_en('Ako ďaleko je tvoj tep nad tvojím pokojom, ako rýchlo stúpa a ako dlho tam drží — z tepu, nie z HRV.',
                                'How far your pulse is above your calm, how fast it climbs and how long it stays there — from heart rate, not HRV.'),
    'metric.load.more': _sk_en(
        'Pruh záťaže sa skladá z troch vecí, ktoré sa z tepu naozaj dajú zistiť: o koľko si nad pokojom, ako rýchlo tep stúpa a ako dlho ostáva hore. Pokoj si beriem z tvojich pokojnejších večerov, nielen z dnešného — keď dnes začínaš vyššie (káva, teplo, únava), pruh ukáže aj to, nielen hru. Slovo nad pruhom hovorí len o tom, kde je tvoj tep práve teraz: „Zvýšená“ je od 10 BPM nad pokojom, „Vysoká“ od 25 BPM a „Špička“ od tvojej hranice vysokého tepu. Kým nemám dosť tvojich relácií, pokoj beriem len z dnešného večera a hranicu priemerného hráča. Pripomienku slovo nespúšťa: keď záťaž prejde prah zo stránky Pripomienky, najprv počítam, či tam chvíľu vydrží, a až potom čakám na pauzu v hre, v ktorej už záťaž nestúpa. Kým slovo ukazuje „Špička“, mlčím. Nie je to HRV ani diagnóza.',
        'The load bar combines three things heart rate can actually tell: how far above your calm you are, how fast it is climbing, and how long it stays up. I take your calm from your calmer evenings, not just tonight — if you start higher today (coffee, heat, fatigue), the bar shows that too, not only the game. The word above the bar is only about where your pulse is right now: “Raised” starts 10 BPM above your calm, “High” at 25 BPM, and “Peak” at your high heart-rate limit. Until I have enough of your sessions, I take your calm from tonight only and use a limit for an average player. The word does not trigger the cue: when the load crosses the threshold on the Cues page, I first count whether it holds there for a while, and only then wait for a pause in the game in which the load is no longer climbing. While the word says “Peak”, I stay quiet. It is not HRV and not a diagnosis.'),
    'metric.hrr.title': _sk_en(
        'Zotavenie tepu',
        'Heart rate recovery'),
    'metric.hrr.short': _sk_en('O koľko ti klesol tep za minútu po tom, čo vyskočil.',
                               'How much your heart rate dropped in the minute after it spiked.'),
    'metric.hrr.more': _sk_en(
        'Hrubý obraz toho, ako rýchlo sa po vypätí vraciaš dole. Väčší pokles = rýchlejšie späť k pokoju. Počíta sa z bežných herných špičiek, nie zo záťažového testu — ber ho ako svoj vlastný trend v čase, nie ako známku kondície.',
        'A rough picture of how fast you come back down after a tense moment. A bigger drop = back to calm sooner. It is read from ordinary gaming spikes, not a fitness test — treat it as your own trend over time, not a fitness score.'),
    'metric.zones.title': _sk_en(
        'Čas nad hranicou tepu a v pásmach',
        'Time over HR limit and in zones'),
    'metric.zones.short': _sk_en('Koľko z relácie bol tvoj tep vysoký.',
                                 'How much of the session you spent with a high heart rate.'),
    'metric.zones.more': _sk_en(
        'Krátke špičky po headshote sú normálne. Dlhý čas nad hranicou môže znamenať, že ťa hra drží v napätí.',
        'Short spikes after a headshot are normal. A long time over the limit can mean the game keeps you tense.'),
    'metric.hrpi.title': _sk_en(
        'Výdrž tepu',
        'HR persistence'),
    'metric.hrpi.short': _sk_en('Jedno číslo, ktoré spája, ako vysoko a ako dlho ti bil tep.',
                                'One number that ties together how high and how long your heart rate ran.'),
    'metric.hrpi.more': _sk_en(
        'Napr. 101 = tep bol aspoň 101 úderov za minútu dokopy aspoň 101 sekúnd. Spája výšku aj trvanie, takže dve relácie porovnáš jedným pohľadom.',
        'E.g. 101 = your heart rate was at least 101 beats per minute for at least 101 seconds in total. It joins height and duration, so you can compare two sessions at a glance.'),
    'metric.zones.calm': _sk_en('pokoj', 'calm'),
    'metric.zones.raised': _sk_en('zvýšená', 'raised'),
    'metric.zones.high': _sk_en('vysoká', 'high'),
    'metric.zones.critical': _sk_en('špička', 'peak'),

    # --- selectable stats on Today (2x2 grid, "Sumi noc" redesign) ---
    'dashboard.stats_title': _sk_en('Moje štatistiky', 'My stats'),
    'dashboard.edit_stats': _sk_en('✎ upraviť', '✎ edit'),
    'dashboard.picker_title': _sk_en('Čo chceš vidieť', 'What you want to see'),
    # quiet line at the bottom of the picker: card limit + how to reorder
    'dashboard.picker_hint': _sk_en(
        'Na Dnes sa zmestia 4 karty. Poradie zmeníš potiahnutím karty na inú — vymenia si miesto.',
        'Today has room for 4 cards. Drag a card onto another to swap their places.'),
    # short name for the card on Today (metric.zones.title is longer, for
    # the expandable science in History - the content of the explanation
    # (.short/.more) is shared, only this title is its own)
    'metric.over.more': _sk_en(
        'Koľko času tvoj tep strávil nad hranicou vysokého tepu. Tú nenastavuješ — počítam si ju z tvojich relácií a pomaly ju dolaďujem (vidíš ju na stránke „{page}“ v karte „Hodinky a tep“). Nie je to známka — krátke špičky patria k hre. Zaujímavé je to, keď číslo večer čo večer rastie pri rovnako dlhom hraní — vtedy sa skús pozrieť, čo sa v tie večery zmenilo.',
        'How long your heart rate stayed above your high heart-rate limit. You do not set it — I compute it from your sessions and slowly fine-tune it (you can see it on the “{page}” page, in the “Watch and heart rate” card). It is not a grade — short spikes are part of playing. It matters when the number grows evening after evening at the same playtime — then see whether something changed on those evenings.'),
    'metric.over.title': _sk_en(
        'Čas nad hranicou tepu',
        'Time over HR limit'),
    # The key 'breath' is historical (from the days of a single breathing
    # slot). It counts ALL automatic cues - the four categories from
    # measure.CATEGORIES alternate (app._dalsi_cue_slot) - so the text must
    # not talk about breathing.
    'metric.breath.title': _sk_en(
        'Pripomienky',
        'Cues'),
    'metric.breath.short': _sk_en(
        'Koľko pripomienok som ti v tejto relácii poslala sama — keď ti záťaž chvíľu držala hore.',
        'How many cues I gave you on my own this session — when your load held up for a while.'),
    'metric.breath.more': _sk_en(
        'Pripomienka je jedna zo štyroch — ťažisko, čeľusť, ruka a pohľad alebo dych — a striedam tie, ktoré máš zapnuté. Počítajú sa len tie, ktoré som poslala sama, keď ti záťaž chvíľu držala hore; tvoje skúšanie tlačidlom „Test“ sa nezaráta. Patria sem aj pripomienky, ktoré prišli len ako obrázok, bez zvuku.',
        'A cue is one of four — grounding, jaw, grip & gaze or breath — and I rotate through the ones you have switched on. Only the ones I gave on my own, when your load held up for a while, count; your own tries with the “Test” button do not. Cues that came as just the picture, without sound, count too.'),
    'metric.avg.title': _sk_en('Priemerný tep dnes', 'Average heart rate today'),
    'metric.avg.more': _sk_en(
        'Jedno číslo za celú reláciu — na porovnanie deň za dňom je užitočnejšia pokojová základňa, tá počíta len tvoje najpokojnejšie chvíle.',
        'One number for the whole session — for day-to-day comparison the resting baseline is more useful, since it only counts your calmest moments.'),
    'metric.max.title': _sk_en('Najvyšší tep', 'Highest heart rate'),
    'metric.max.more': _sk_en(
        'Jedna špička sama o sebe nič nehovorí — dôležitejšie je, ako rýchlo sa tep po nej vrátil dole (zotavenie HRR).',
        'A single spike says little on its own — what matters more is how fast your heart rate came back down afterward (HRR).'),
    'metric.peak.title': _sk_en('Špička záťaže', 'Peak load'),
    'metric.peak.short': _sk_en(
        'Najvyššia hodnota záťaže (0–100) počas dnešnej relácie.',
        "The highest load value (0-100) during today's session."),
    'metric.peak.more': _sk_en(
        'Záťaž skladá tri veci z tepu: o koľko si nad pokojom, ako rýchlo tep stúpa a ako dlho ostáva hore. Špička záťaže je najvyšší okamih tejto kombinácie.',
        'Load combines three things from your heart rate: how far above resting you are, how fast it is climbing, and how long it stays up. Peak load is the single highest moment of that combination.'),
    'metric.week.title': _sk_en('Relácie tento týždeň', 'Sessions this week'),
    'metric.week.more': _sk_en(
        'Týždeň sa počíta od pondelka a rátajú sa len relácie sveta, v ktorom práve si (Hra alebo Práca). Slúži len na prehľad, koľko som toho tento týždeň zaznamenala.',
        'The week counts from Monday, and only sessions of the world you are in (Play or Work) count. It is just an overview of how much I have logged this week.'),
    # --- 0.2 (widgets-history): five new cards. Each says what it measures
    # and what it does NOT measure; no score, grade or streak. History shows
    # the same texts (length, rest and signal under the chart; felt/measured
    # under the table), so `short` does not talk only about the live card.
    'metric.session_len.title': _sk_en('Dĺžka relácie', 'Session length'),
    'metric.session_len.short': _sk_en(
        'Ako dlho relácia trvá — odkedy som začala sledovať.',
        'How long the session runs — since I started watching.'),
    'metric.session_len.more': _sk_en(
        'Relácia začína, keď začnem sledovať, nie keď spustíš hru, a končí, keď sledovanie zastavíš. Sú to len hodiny, nie hodnotenie: dlhá relácia nie je zlá a krátka nie je dobrá. Keď práve nesledujem, karta ukáže „—“.',
        'A session starts when I start watching, not when you launch the game, and ends when you stop watching. It is just a clock, not a rating: a long session is not bad and a short one is not good. When I’m not watching right now, the card shows “—”.'),
    'metric.last_cue.title': _sk_en(
        'Od poslednej pripomienky',
        'Since the last cue'),
    'metric.last_cue.more': _sk_en(
        'Počíta sa len pripomienka, ktorú som poslala sama a naozaj sa ukázala — tvoje skúšanie tlačidlom „Test“ sa nezaráta. Kým v tejto relácii žiadna neprišla, karta ukáže „—“. Nie je to cieľ ani séria: dlhé ticho neznamená, že sa ti darí, a pripomienka neznamená, že robíš niečo zle. Je to len to, kedy som sa ozvala naposledy.',
        'Only a cue I gave on my own and that actually showed counts — your own tries with the “Test” button do not. Until one comes this session, the card shows “—”. It is not a goal or a streak: a long silence does not mean you are doing well, and a cue does not mean you are doing something wrong. It is just when I last spoke up.'),
    'metric.calm_time.title': _sk_en('Čas v pokoji', 'Time in calm'),
    'metric.calm_time.short': _sk_en(
        'Koľko minút relácie bol tvoj tep v pásme pokoja.',
        'How many minutes of the session your pulse spent in the calm zone.'),
    'metric.calm_time.more': _sk_en(
        'Pokoj je to isté pásmo ako v paneli „Kde bol dnes tep“: tep menej ako 10 BPM nad tvojím pokojom. Hovorí o tepe, nie o tom, ako pokojne sa cítiš. Nie je to skóre — viac minút neznamená lepší večer; napätý zápas tep zdvihne a tak to má byť. Na prvom večeri, kým tvoj pokoj ešte nepoznám, karta ukáže „—“.',
        'Calm is the same zone as in the “Where the session went” panel: a pulse less than 10 BPM above your calm. It is about your heart rate, not about how calm you felt. It is not a score — more minutes do not mean a better evening; a tense match raises your pulse, and that is how it should be. On your first evening, until I know your calm, the card shows “—”.'),
    'metric.signal.title': _sk_en('Kvalita signálu', 'Signal quality'),
    'metric.signal.short': _sk_en(
        'Ako dobre prijímam tvoj tep: akú časť relácie naozaj chodil.',
        'How well I receive your heart rate: what share of the session it actually came through.'),
    'metric.signal.more': _sk_en(
        'Percento je čas, keď tep naozaj chodil, z času od prvej vzorky. Číslo za „·“ na karte je, koľkokrát v tejto relácii tep vypadol — keď ani raz, nie je tam. Percento sa na karte ukáže až po minúte, skôr by jedna medzera vyzerala ako zlé spojenie. Hovorí o ceste hodinky → telefón → Wi‑Fi → počítač, nie o tvojom srdci ani o tebe. Keď je nízke, pripomienok môže byť menej: keď tep vypadne uprostred počítania, začnem počítať odznova. V Histórii sa ráta z celej relácie aj s čakaním, kým začal chodiť tep, preto tam krátke relácie vychádzajú nižšie.',
        'The percentage is the time your heart rate actually came through, out of the time since the first sample. The number after “·” on the card is how many times it dropped out this session — if it never did, it is not there. The card shows the percentage only after a minute; sooner, a single gap would look like a bad connection. It is about the path watch → phone → Wi‑Fi → PC, not about your heart or about you. When it is low, there may be fewer cues: when your heart rate drops out in the middle of counting, I start counting again. In History it is computed over the whole session, including the wait until your heart rate started coming in, so short sessions come out lower there.'),
    'metric.felt_vs_measured.title': _sk_en('Cítené a merané', 'Felt and measured'),
    'metric.felt_vs_measured.short': _sk_en(
        'Tvoja vnímaná záťaž z dotazníka vedľa nameranej špičky záťaže, obe 0–10.',
        'Your felt load from the questionnaire next to the measured peak load, both 0–10.'),
    'metric.felt_vs_measured.more': _sk_en(
        'Karta na Dnes berie poslednú ukončenú reláciu tohto sveta (Hra alebo Práca), detail v Histórii tú, ktorá je vybraná. Prvé číslo je tvoje hodnotenie záťaže v dotazníku po relácii. Druhé je najvyššia záťaž tej istej relácie (špička 0–100) vydelená desiatimi. Nemusia sa zhodovať a ani jedno nie je „to správne“ — tep nevidí, ako ti bolo, a ty necítiš každý úder. Rozdiel medzi nimi nie je chyba, je to informácia. Keď ostal dotazník preskočený, ukáže „—“.',
        'The card on the Today page takes your last finished session in this world (Play or Work); the detail in History takes the one you picked. The first number is how you rated the load in the questionnaire after the session. The second is the highest load of that same session (the 0–100 peak) divided by ten. They do not have to match, and neither is “the right one” — your pulse cannot see how it felt, and you do not feel every beat. A gap between them is not an error, it is information. If you skipped the questionnaire, it shows “—”.'),
    'dashboard.unit.baseline': _sk_en('BPM', 'BPM'),
    'dashboard.unit.hrr': _sk_en('BPM za minútu', 'BPM per minute'),
    'dashboard.unit.over': _sk_en('za dnešnú reláciu', "this session"),
    'dashboard.unit.breath': _sk_en('automaticky', 'automatic'),
    'dashboard.unit.avg': _sk_en('za reláciu', 'this session'),
    'dashboard.unit.max': _sk_en('za reláciu', 'this session'),
    'dashboard.unit.peak': _sk_en('z 0–100', 'of 0-100'),
    'dashboard.unit.session_len': _sk_en('od začiatku relácie', 'since the session began'),
    'dashboard.unit.last_cue': _sk_en(
        'od poslednej pripomienky',
        'since the last cue'),
    'dashboard.unit.calm_time': _sk_en('v pokoji za reláciu', 'in calm this session'),
    'dashboard.unit.signal': _sk_en('času s tepom', 'of the time with a pulse'),
    'dashboard.unit.felt_vs_measured': _sk_en('cítené · merané, 0–10', 'felt · measured, 0–10'),
    # Number format on the cards and in the session detail - as a key, so
    # that the language phase can translate it (e.g. 分). {m} already comes
    # as two digits.
    'dashboard.fmt.min': _sk_en('{n} min', '{n} min'),
    'dashboard.fmt.h_min': _sk_en('{h} h {m} min', '{h} h {m} min'),
    'dashboard.fmt.pct': _sk_en('{n} %', '{n}%'),

    # --- recommendations from the background analysis (insights, not
    # diagnoses) ---
    # Recommendations about SILENCE. The only ones that tell the player what
    # to do - so they rest on numbers from the trigger, not on an impression
    # from heart rate.
    # {n} = the average over the last evenings (`hr_insights`), not the sum.
    # The advice is the same as in `session.end.none_dropouts` - one truthful
    # chain.
    'insight.cue_dropouts': _sk_en(
        'Tep ti v posledných reláciách vypadával priemerne {n}× na reláciu práve počas počítania a počítanie sa zakaždým začalo odznova — preto môže byť pripomienok menej. Tep ide z hodiniek do telefónu cez Bluetooth a z telefónu cez Wi‑Fi do počítača — maj hodinky pri telefóne a telefón blízko Wi‑Fi routra. Keď odchádzaš od počítača, vezmi telefón so sebou.',
        'In your recent sessions your heart rate dropped out {n}× per session on average while I was counting, and each time the count started over — so there may be fewer cues. It goes from the watch to the phone over Bluetooth, and from the phone to the PC over Wi‑Fi — keep the watch near the phone and the phone near the Wi‑Fi router. When you step away from the PC, take the phone with you.'),
    'insight.cue_never_above': _sk_en(
        'V posledných {n} reláciách sa záťaž ani raz nedostala nad prah — nemala som prečo sa ozvať. Prah nie je nastavenie: počítam si ho z tvojich relácií a posúvam ho, ako ťa spoznávam. Aktuálny vidíš v Nastaveniach → Pripomienky.',
        'In your last {n} sessions your load never crossed the threshold, so I had no reason to speak up. The threshold is not a setting — I compute it from your sessions and move it as I get to know you. You can see the current one in Settings → Cues.'),
    'insight.cue_almost': _sk_en('Záťaž hore bola, ale najdlhšie {sec} s v kuse — chýbalo do {need} s. Bolo to tesne. Zámerne čakám, kým záťaž vydrží hore, aby som sa neozývala pri každej krátkej špičke.',
                                  'Your load did rise, but the longest stretch was {sec} s — short of {need} s. It was close. I wait on purpose for the load to hold, so I do not speak up at every short spike.'),
    'insight.cue_far': _sk_en(
        'Záťaž sa nad prah dostala, ale len na chvíľu — najdlhšie {sec} s z potrebných {need} s. Tvoje telo ide hore a dole rýchlejšie, než čakám. Na krátke špičky sa zámerne neozývam — nastavovať tu nie je čo.',
        'Your load did cross the threshold, but only briefly — the longest stretch was {sec} s out of the {need} s I need. Your body rises and falls faster than I wait. I stay quiet on short spikes on purpose — there is nothing to set here.'),
    'insight.need_more': _sk_en(
        'Zatiaľ {n} z {need} relácií — po troch začnem hľadať vzory naprieč nimi.',
        '{n} of {need} sessions so far — after three I start looking for patterns across them.'),
    'insight.resting_up': _sk_en(
        'Pokojová základňa je v posledných reláciách o {delta} BPM vyššia než v tých predtým — možno menej spánku, kofeín alebo nachladnutie? Nie je to nutne z hrania.',
        'Your resting baseline is {delta} BPM higher in recent sessions than in the ones before — maybe less sleep, caffeine or a cold? Not necessarily from gaming.'),
    'insight.resting_down': _sk_en(
        'Pokojová základňa je v posledných reláciách o {delta} BPM nižšia než v tých predtým. Môže to byť lepší spánok, menej kofeínu alebo len pokojnejšie chvíle pri meraní — jedno číslo to nerozlíši.',
        "Your resting baseline is {delta} BPM lower in recent sessions than in the ones before. It could be better sleep, less caffeine, or just calmer moments while measuring — one number can't tell which."),
    'insight.hrr_up': _sk_en(
        'Zotavenie tepu je v posledných reláciách o {delta} BPM rýchlejšie než predtým. Pekný signál — ale z pár relácií je to skôr náznak než istota.',
        'Heart rate recovery has been {delta} BPM faster in recent sessions than before. A good sign — though from a few sessions it is a hint, not a certainty.'),
    'insight.hrr_down': _sk_en(
        'Zotavenie tepu je v posledných reláciách o {delta} BPM pomalšie než predtým. Z pár relácií je to skôr náznak — záleží aj na tom, ako vysoko tep vyskočil, a môže za tým byť spánok, únava či iný typ hier.',
        'Heart rate recovery has been {delta} BPM slower in recent sessions than before. From a few sessions it is a hint, not a certainty — it also depends on how high your pulse went, and sleep, tiredness or a different kind of game can play a part.'),
    'insight.triggers_early': _sk_en(
        'V reláciách od 1,5 h prišlo {share} % pripomienok v prvej hodine. Ak sa to opakuje, možno ťa rozbieha práve začiatok — skús pokojnejší rozjazd a sleduj, či sa to zmení.',
        "In sessions of 1.5 h or longer, {share} % of my cues came in the first hour. If that keeps happening, the start of a session may be what winds you up — try a calmer warm-up and see if it changes."),
    'insight.triggers_late': _sk_en(
        'V reláciách od 2,5 h prišlo {share} % pripomienok až po dvoch hodinách — dlhé relácie ťa môžu držať v napätí; skús kratšie relácie s prestávkou.',
        "In sessions of 2.5 h or longer, {share} % of my cues came after the first two hours — long sessions may keep you tense; try shorter sessions with a break."),
    'insight.over_up': _sk_en(
        'V posledných reláciách bol tvoj tep nad hranicou väčšiu časť relácie než predtým (priemer {minutes} min). Môže za tým byť hra, ale aj spánok či kofeín — alebo len to, že si hranicu po každej relácii dolaďujem podľa tvojich dát. Ak to tak ostane, môžeš skúsiť dýchanie zo Sprievodcu.',
        'You have spent a bigger share of your sessions over the limit recently than before (average {minutes} min). It could be the game — or sleep or caffeine — or simply that I fine-tune your limit from your own data after each session. If it stays that way, you could try the breathing from the Guide.'),
    'insight.steady': _sk_en(
        'V {n} reláciách som si zatiaľ nič nevšimla.',
        "I haven't noticed anything across {n} sessions so far."),

    # --- three sources in the app (guide_content.PHILOSOPHY_SOURCES) ---
    # 0.2: the labels are the author's examples under the "How it came
    # about" text, not study titles. The other sources (source1-9, 13-17)
    # left the app for ZDROJE.md.
    'guide.philosophy.source12': _sk_en(
        'pri výdychu sa tep prirodzene spomalí (Lehrer & Gevirtz, 2014)',
        'your heart naturally slows as you breathe out (Lehrer & Gevirtz, 2014)'),
    'guide.philosophy.source11': _sk_en(
        'pomalé dýchanie sa spája s pokojnejším stavom (Zaccaro a kol., 2018)',
        'slow breathing goes together with a calmer state (Zaccaro et al., 2018)'),
    'guide.philosophy.source10': _sk_en(
        'súťažné hranie spúšťa skutočnú stresovú reakciu srdca (Ketelhut & Nigg, 2024)',
        'competitive play triggers a real stress response in the heart (Ketelhut & Nigg, 2024)'),

    # --- onboarding step 3: a second reason for the watch (history) ---
    'ob.step3.body2': _sk_en(
        'Appka si pamätá každú reláciu. Po pár týždňoch ti ukáže tvoje trendy, napríklad ako rýchlo sa po vypätí upokojuješ — orientačne, z hodiniek, nie ako diagnóza.',
        'The app remembers every session. After a few weeks it shows your trends, like how fast you settle after a tense moment — a rough guide from the watch, not a diagnosis.'),

    # --- pairing: more addresses ---
    'hr.pair_other_ips': _sk_en(
        'Ďalšie adresy tohto PC (ak hodinky prvú nevidia, skús tieto — každá je iná sieť/adaptér): {ips}',
        'Other addresses of this PC (if the watch cannot reach the first one, try these — each is a different network/adapter): {ips}'),
    'hr.pair_ip_note': _sk_en(
        'Toto je adresa počítača v tvojej sieti. V nastaveniach nechaj 0.0.0.0 — appka počúva na všetkých sieťach naraz, toto číslo sa píše len do telefónu.',
        'This is your PC’s address on your network. Keep 0.0.0.0 in settings — the app listens on every network at once; this number only goes into the phone.'),
    'history.sessions_count': _sk_en('{n} relácií', '{n} sessions'),
    'history.minutes': _sk_en('{m} min', '{m} min'),
})


# --- UX feedback from a live test: a uniform friendly tone (informal
# "you"), shorter pairing, new menu (Settings as a group), dock. The
# rewrites OVERWRITE the older formal wordings above (STRINGS.update) -
# sk/en by hand, the other 7 languages in English for now
# (preklad_TODO.csv). Still factual and clear, just human.
STRINGS.update({
    # --- navigation: 3 main items, the rest are tabs in Settings ---
    'nav.nastavenia_tabs.spustace': _sk_en(
        'Pripomienky',
        'Cues'),
    'nav.nastavenia_tabs.zvuk': _sk_en('Zvuk', 'Sound'),
    'nav.nastavenia_tabs.vseobecne': _sk_en('Všeobecné', 'General'),
    # NOTE: 'dock.mute_tip', 'dock.unmute_tip', 'dock.snooze_tip' and
    # 'dock.profile_tip' left with the quick dock (see app.py, `_build_ui`).
    # These two stayed - the status dot in the row and the heart rate
    # indicator carry them. 24. 9.: the text carries the end time, not the
    # remaining minutes - it is set once and "zostava 30 min" (30 min left)
    # would soon be wrong. Nothing about measuring: the shortcut works even
    # when the app is not listening, and then "merám ďalej" (I keep
    # measuring) would be a lie.
    'dock.snooze_active_tip': _sk_en('Teraz nie — do {until} sa neozvem',
                                     "Not now — I won't speak up until {until}"),
    'dock.pulse_live_tip': _sk_en('Tep z hodiniek beží', 'Heart rate is live'),
    # Main switch on Today (0.3 batch 4): one button with text in the
    # breathing bar (`ui_kit.KamaeBar`). The same words as in the tray icon
    # menu (`tray.start` / `tray.stop`), just with a symbol.
    'dock.start': _sk_en('▶ Spustiť sledovanie', '▶ Start watching'),
    'dock.stop': _sk_en('■ Zastaviť sledovanie', '■ Stop watching'),
    'dock.start_tip': {
        'sk': 'Spusti sledovanie — začnem sa ozývať.',
        'en': 'Start watching — I’ll start speaking up.',
        'ja': '見守りを開始 — 合図を出すようになります。',
        'zh': '开始关注——我会开始提醒你。',
        'ru': 'Начать наблюдение — я начну подавать знаки.',
        'es': 'Empieza a observar: empezaré a avisarte.',
        'de': 'Beobachtung starten — ich fange an, mich zu melden.',
        'fr': 'Lancer l’observation — je commence à me manifester.',
        'pt': 'Começar a observar — vou começar a avisar.',
    },
    'dock.stop_tip': _sk_en(
        'Zastav sledovanie — neozvem sa, kým ma znova nespustíš.',
        'Stop watching — I won’t speak up until you start me again.'),
    # The 😴 button no longer silences for a hard 20 minutes - it opens a
    # choice of length.
    # NOTE: 'dnes.empty_title' ("Tu uvidíš svoj tep", Here you will see your
    # heart rate) left with the HUD preview from the empty state (0.3 batch
    # 4) - the empty state is one sentence and one action
    # (`ui_kit.EmptyState`), the heading above it only repeated the panel
    # heading.
    'dnes.empty_body': _sk_en(
        'Keď spáruješ hodinky, budem ti sem kresliť tep a záťaž — a keď ti záťaž chvíľu drží hore, ozvem sa sama pripomienkou.',
        'Once you pair your watch, I’ll draw your heart rate and load here — and when your load holds up for a while, I’ll give you a cue on my own.'),
    'dnes.empty_btn': _sk_en('Spárovať hodinky', 'Pair your watch'),

    # --- Sound and voice: no abbreviations (TTS, SFX, SAPI5) in labels ---
    'settings.volume': _sk_en('Hlasitosť:', 'Volume:'),
    'settings.balance': _sk_en('Pomer zvuk ↔ hlas:', 'Sound ↔ voice mix:'),
    'settings.balance_center': _sk_en('napoly', 'even'),
    'settings.balance_sfx': _sk_en('zvuk', 'sound'),
    'settings.balance_tts': _sk_en('hlas', 'voice'),
    'settings.engine': _sk_en(
        'Zdroj hlasu',
        'Voice source'),
    'settings.voice': _sk_en('Hlas:', 'Voice:'),
    'settings.rate': _sk_en('Rýchlosť reči:', 'Speech speed:'),
    'engine.edge': _sk_en(
        'Prirodzený (online, Microsoft)',
        'Natural (online, Microsoft)'),
    'engine.sapi': _sk_en(
        'Windows (bez internetu)',
        'Windows (offline)'),
    'mode.tts': _sk_en('Hlas', 'Voice'),
    'mode.sfx': _sk_en('Zvuk', 'Sound'),
    'mode.combo': _sk_en('Hlas + zvuk', 'Voice + sound'),

    # --- Cues ---
    # PHASE 3: the key no longer triggers anything, so the original text
    # ("several triggers can have the same key") would be a lie. Redrawing
    # the whole page is phase 5; this is the minimum so that the app does
    # not tell untruths.
    'slots.title': _sk_en(
        'Čo poviem',
        'What I say'),
    # 0.2 (stress-gate): the same timing as `tour.triggers.body`.
    'slots.hint': _sk_en(
        'Kedy sa ozvem, rozhoduje tvoj tep: keď záťaž chvíľu drží hore, počkám na pauzu, v ktorej už nestúpa; v pásme Špička mlčím. Tu nastavíš, čo poviem.',
        'Your heart rate decides when I speak up: when your load holds up for a while, I wait for a pause in which it is no longer climbing; in the peak zone I stay quiet. Here you set what I say.'),
    'settings.auto_profile': _sk_en(
        'Pri známej hre sama prepnem profil a spustím sledovanie',
        'When a game I know is running, I switch the profile and start watching by myself'),
    # Exactly what the switch does - and that when it is off the processes
    # are not read at all (`GameProcessWatcher` does not run then). {games}
    # = `game_profiles.known_games`.
    'settings.auto_profile_sub': _sk_en(
        'Hry, ktoré poznám: {games}. Každých pár sekúnd pozriem len názvy bežiacich programov. Keď hru nájdem, prepnem na jej profil a spustím sa; keď ju zavrieš, zastavím sa (ak som sa spustila sama). Vypnuté = názvy programov nečítam.',
        'Games I know: {games}. Every few seconds I look only at the names of running programs. When I find a game, I switch to its profile and start; when you close it, I stop (if I started by myself). Off = I don’t read program names.'),
    'settings.auto_profile_unavailable': _sk_en(
        'Automatické prepínanie podľa hry teraz nejde (chýba knižnica psutil)',
        'Automatic switching by game is unavailable right now (psutil library missing)'),

    # --- In game ---
    'overlay.dialog_title': _sk_en(
        'Obrázky v hre',
        'In-game pictures'),
    'overlay.monitor.label': _sk_en('Na ktorej obrazovke kresliť', 'Which screen to draw on'),
    'hud.section_title': _sk_en('Panel s tepom v hre', 'Heart-rate panel in game'),
    'hud.enable': _sk_en('Ukázať panel v hre — pre stream',
                         'Show the panel in game — for streaming'),
    # PHASE 3: the panel stays, but the description says WHO it is FOR. A
    # permanently shown heart rate while playing is distracting - a bar is
    # perceived peripherally, but a number has to be read, and that is
    # exactly the attention the app is supposed to save. For a viewer on a
    # stream, on the other hand, it makes sense. That is why it is off and
    # why this is written here.
    'hud.hint': _sk_en(
        'Malý panel v rohu: tvoj tep, krivka za posledné 3 minúty, záťaž a priebeh relácie. Divákom na streame dáva zmysel; tebe počas hrania skôr uberá pozornosť, preto je vypnutý. Klik cezeň prejde do hry a v Alt+Tab ho neuvidíš.',
        'A small corner panel: your heart rate, the last 3 minutes, load and session progress. It makes sense for stream viewers; while you play it mostly costs you attention, which is why it is off. Clicks pass through to the game and it never shows in Alt+Tab.'),
    # For the first ~30 samples of a session the app does not have your
    # baseline yet. Instead of load against a rough estimate, the HUD and
    # Today show this (hud_paint.render_hud).
    'hud.calibrating': _sk_en('kalibrujem…', 'calibrating…'),
    'settings.hr_section_title': _sk_en('Hodinky a tep', 'Watch and heart rate'),
    'settings.hr_enable_switch': _sk_en(
        'Prijímať tep z telefónu',
        'Receive heart rate from the phone'),
    'settings.hr_ip_hint': _sk_en(
        'Nechaj 0.0.0.0. Do telefónu toto číslo nepíš — správnu adresu nájdeš v „Ako spárovať hodinky…“.',
        'Leave 0.0.0.0. Don’t type this number into the phone — the right address is in “How to pair your watch…”.'),
    'settings.hr_port_hint': _sk_en(
        'Nechaj 4455 — to isté číslo zadáš v appke v telefóne.',
        'Leave 4455 — you enter the same number in the phone app.'),

    # --- Guide ---
    'guide.panel_subtitle': _sk_en(
        'Čo sa ti v tele deje pri každej pripomienke a čo s tým spraviť, keď sa appka ozve.',
        'What happens in your body at each cue and what to do about it when the app speaks up.'),
    'guide.block.physiology': _sk_en('Čo sa deje v tele', 'What happens in your body'),
    # Not „Čo na to veda“ (What science says): the block is partly practice,
    # partly a few cited studies - the heading must not promise more than
    # the text under it gives.
    'guide.block.science': _sk_en('Prečo to môže pomôcť', 'Why it may help'),
    'guide.block.instruction': _sk_en(
        'Čo môžeš urobiť',
        'What you can do'),
    # KNOWN_ISSUES.md #5: "it is not a medical device" no longer only in
    # the README. One quiet sentence, not a warning - the same tone as
    # 'history.insights_note' („postrehy a tipy, nie diagnózy“ - insights
    # and tips, not diagnoses).
    'guide.not_medical_note': _sk_en(
        'Sú to všeobecné tipy pre pohodu, nie lekárska rada — Zanshin nie je zdravotnícka pomôcka. Ak máš ťažkosti so srdcom alebo s dýchaním, najprv sa poraď s lekárom.',
        'These are general wellbeing tips, not medical advice — Zanshin is not a medical device. If you have heart or breathing problems, check with a doctor first.'),
    'settings.guide_row': _sk_en('Prečo práve čeľusť, ťažisko a dych', 'Why jaw, balance and breath'),

    # --- watch pairing: steps stay, text shorter (it was a wall of text) ---
    'hr.pair_intro': _sk_en(
        'Tep ti do počítača pošle appka v telefóne. Zanshin sa jej tvári ako OBS — samotné OBS inštalovať nemusíš.',
        'The app on your phone sends your heart rate to this PC. To it, Zanshin looks like OBS — you don’t need to install OBS itself.'),
    'hr.step1_body': _sk_en(
        'Telefón aj počítač na tej istej Wi‑Fi (nie mobilné dáta). Windows sa teraz môže spýtať, či Zanshin pustiť do siete — povoľ len súkromné (domáce) siete.',
        'Phone and PC on the same Wi‑Fi (not mobile data). Windows may now ask whether to let Zanshin onto the network — allow private (home) networks only.'),
    'hr.step2_body': _sk_en(
        'Android / Wear OS: „HeartRateOnStream for OBS“ z Google Play (zdarma). iPhone / Apple Watch: „PulseOSC“ z App Store (platená, zatiaľ nevyskúšaná — autor nemá Apple). Heslo, scéna a zdroj (kroky 3–4) platia len pre appku na Androide. Naskenuj kód nižšie a prepoj appku s hodinkami.',
        'Android / Wear OS: “HeartRateOnStream for OBS” from Google Play (free). iPhone / Apple Watch: “PulseOSC” from the App Store (paid, untested so far — the author has no Apple device). The password, scene and source (steps 3–4) apply to the Android app only. Scan a code below and connect the app to your watch.'),
    'hr.step3_body': _sk_en('V appke na telefóne zadaj adresu a port z rámika hore. Heslo nechaj prázdne.',
                            'In the phone app enter the address and port from the box above. Leave the password empty.'),
    'hr.step4_body': _sk_en('Po pripojení vyber scénu „Zanshin“ a zdroj „Tep“. Ak vieš posielať aj kroky a rýchlosť, sú tam zdroje „Kroky“ a „Rychlost“.',
                            'Once connected, pick the scene “Zanshin” and the source “Tep”. If you can also send steps and speed, the sources “Kroky” and “Rychlost” are there too.'),
    'hr.step5_body': _sk_en(
        'Otvorením tohto návodu sa príjem tepu zapol — netreba nič prepínať. Keď pod adresou uvidíš tep v BPM, je hotovo.',
        'Opening this guide switched heart-rate receiving on — no need to flip anything. When you see your heart rate in BPM under the address, you’re done.'),
    # 0.3: the phone does not connect AT ALL - a different case from
    # trouble_* (connects, heart rate does not come). Menu names: sk
    # verified on a Slovak Windows 11 (Settings, Windows Security), the
    # other languages according to Microsoft terminology - fix when a
    # player reports it.
    'hr.noconnect_title': _sk_en(
        'Hodinky sa vôbec nepripoja?',
        'Watch won’t connect at all?'),
    'hr.noconnect_body': _sk_en(
        '1) Telefón aj PC na tej istej Wi‑Fi — nie mobilné dáta, hosťovská sieť ani VPN.\n2) Adresa v telefóne musí sedieť s tou hore — po reštarte routera sa mení.\n3) Nastavenia → Sieť a internet → Wi‑Fi (alebo Ethernet) → tvoja sieť → Typ profilu siete: Súkromná sieť.\n4) Windows Zabezpečenie → Firewall a ochrana siete → Povoliť aplikáciu v bráne firewall → Zmeniť nastavenie → pri Zanshin zaškrtni Súkromné.',
        '1) Phone and PC on the same Wi‑Fi — not mobile data, a guest network or a VPN.\n2) The address in the phone must match the one above — it changes after a router restart.\n3) Settings → Network & internet → Wi‑Fi (or Ethernet) → your network → Network profile type: Private network.\n4) Windows Security → Firewall & network protection → Allow an app through firewall → Change settings → tick Private next to Zanshin.'),
    'hr.trouble_body': _sk_en(
        'Skontroluj scénu „Zanshin“ a zdroj „Tep“ v telefóne a či hodinky naozaj merajú. Ak port obsadil iný program, zmeň ho tu aj v telefóne.',
        'Check the “Zanshin” scene and “Tep” source on the phone, and that the watch is actually measuring. If another program took the port, change it here and on the phone.'),
    'hr.pair_other_ips': _sk_en('Ďalšie adresy tohto PC (ak prvá nejde): {ips}',
                                'Other addresses of this PC (if the first does not work): {ips}'),
    'hr.pair_ip_note': _sk_en('V nastaveniach nechaj 0.0.0.0 — toto číslo ide len do telefónu.',
                              'Keep 0.0.0.0 in settings — this number only goes into the phone.'),
    # 0.2 hidden IP: the PC's address is not shown on screen by itself
    # (stream, screenshot) - only on a click, and only until the app restarts
    # (netinfo.mask_ip).
    'hr.ip_show': _sk_en('Ukázať IP', 'Show IP'),
    'hr.ip_hide': _sk_en('Skryť IP', 'Hide IP'),
    'hr.ip_hidden_note': _sk_en(
        'Adresu skrývam, aby ju nebolo vidno na streame ani na screenshote. Do telefónu ju prepíšeš po kliku na „Ukázať IP“.',
        'I keep the address hidden so it does not show up on a stream or in a screenshot. Click “Show IP” to copy it into the phone.'),
    # 0.3: live status under the address in the pairing window
    # (`ui_dialogs.stav_parovania`).
    'hr.pair_status_waiting': _sk_en(
        '● Čakám, kým sa telefón pripojí…',
        '● Waiting for the phone to connect…'),
    'hr.pair_status_no_client': _sk_en(
        '● Telefón sa zatiaľ nepripojil. Čo skontrolovať, je nižšie.',
        '● The phone hasn’t connected yet. What to check is below.'),
    'hr.pair_status_linked': _sk_en(
        '● Telefón pripojený — čakám na tep…',
        '● Phone connected — waiting for heart rate…'),
    'hr.pair_status_ok': _sk_en(
        '✓ Tep chodí: {bpm} BPM. Okno môžeš zavrieť.',
        '✓ Heart rate is coming in: {bpm} BPM. You can close this window.'),
    'hr.pair_status_busy': _sk_en(
        '● Port {port} drží iný program — skúšam znova…',
        '● Another program holds port {port} — trying again…'),
    'hr.pair_status_gave_up': _sk_en(
        '✕ Port {port} drží iný program. Zmeň ho na stránke „{page}“ a rovnaké číslo zadaj v telefóne.',
        '✕ Another program holds port {port}. Change it on the “{page}” page and enter the same number on the phone.'),
    'hr.pair_status_off': _sk_en(
        '✕ Príjem tepu sa nezapol. Zavri toto okno a otvor ho znova — skúsim to ešte raz.',
        '✕ Heart-rate receiving didn’t start. Close this window and open it again — I’ll try once more.'),

    # --- breath cycle adjustable in seconds (In-game visuals -> Breath slot) ---
    'overlay.breath_seconds': _sk_en('Dychový cyklus (v sekundách)',
                                     'Breathing cycle (in seconds)'),
    'overlay.breath_inhale': _sk_en('Dĺžka nádychu (s)', 'Inhale length (s)'),
    'overlay.breath_exhale': _sk_en('Dĺžka výdychu (s)', 'Exhale length (s)'),
    # --- the ring at high heart rate (off by default, Breath card, below the
    # inhale/exhale lengths). Settings texts only - in the game the ring
    # shows the usual inhale/exhale captions. ---
    'overlay.high_hr_ring': _sk_en('Kruh aj pri vysokom tepe',
                                   'Ring at high heart rate too'),
    'overlay.high_hr_ring_bpm': _sk_en('Nad {bpm} BPM', 'Above {bpm} BPM'),
    # {margin} = how far below the limit the heart rate must drop before the
    # ring finishes (`app_session.KRUH_TEP_REZERVA_BPM`, 3).
    'overlay.high_hr_ring_hint': _sk_en(
        'Dychový kruh sa ukáže, keď tep prekročí túto hranicu, a dýcha dokola, '
        'kým neklesne aspoň o {margin} BPM pod ňu; potom skončí po výdychu. '
        'Medzitým nepríde iná pripomienka.',
        'The breath ring shows when your heart rate goes above this limit and keeps '
        'breathing until it drops at least {margin} BPM below it; then it ends after '
        'an exhale. No other cue comes meanwhile.'),
    # The same switch as a quick row on Today, under the HUD one (upper case
    # there). The limit is set in In-game pictures, ⚙ next to it.
    'dnes.high_hr_ring_quick': _sk_en('Dychový kruh nad {bpm} BPM',
                                      'Breath ring above {bpm} BPM'),

    # NOTE: the whole 'minimalist mode' section was here -
    # 'settings.minimal_mode', 'settings.minimal_mode_sub', 'minimal.expand_tip'
    # and 'log.minimal_mode_on/off'. The app-wide switch was removed, so
    # nothing called these keys any more (orphaned ballast that on top of that
    # was dragged into preklad_TODO.csv as 3 more strings to translate into 7
    # languages). The same function (BPM + 4 icons) is now part of the HUD
    # panel in game ("Show the panel in game" in the visuals), not a switch
    # of the whole app window. See 'hud.trigger_row.*' below.
    # The switch says WHAT it shows (the icons), not "the panel": 'hud.enable'
    # a bit higher up starts with "Ukázať panel v hre", and two different
    # switches with one label could not be told apart.
    'hud.trigger_row.toggle': _sk_en('Ukázať ikonky v hre', 'Show icons in-game'),
    'hud.trigger_row.sub': _sk_en(
        'Pod panelom s tepom sa ukážu ikonky tvojich štyroch pripomienok. Sú len na pohľad a obrázky v hre nenahrádzajú — pripomienka potrebuje aspoň jeden z nich zapnutý.',
        'Shows the icons of your four cues under the heart-rate panel. They are only for show and do not replace the in-game pictures — a cue needs at least one of those turned on.'),
    'hud.trigger_row.color': _sk_en('Farba ikoniek', 'Icon colour'),
    # NOTE: 'hud.snooze.title' ("Stíšiť appku na…", Silence the app for…) was
    # here as the heading of the row with the cog wheel on the In game page.
    # The choice of length moved into the dock (the 😴 button), where no
    # heading is needed - the tooltip carries it.
    'hud.snooze.5min': _sk_en('5 minút', '5 minutes'),
    'hud.snooze.20min': _sk_en('20 minút', '20 minutes'),
    'hud.snooze.40min': _sk_en('40 minút', '40 minutes'),
    'hud.snooze.60min': _sk_en('60 minút', '60 minutes'),
    'hud.snooze.cancel': _sk_en('Zrušiť stíšenie', 'Cancel snooze'),
    'log.hotkey_on': _sk_en('Klávesová skratka {combo} je pripravená — stíši ma na pol hodiny', 'Hotkey {combo} is ready — it will quiet me for half an hour'),
    # 24. 9.: "not now" is no longer a stop - the switch in the bar and the
    # icon in the tray stop measuring too, so the sentence says it plainly.
    # 0.2.1: this sentence goes into the journal only WITHOUT a tray icon
    # (pystray/PIL error) - with the tray it is `log.hotkey_failed_tray`. So
    # it does not name the tray icon: where it is shown, there is none.
    'log.hotkey_failed': _sk_en('Skratku {combo} drží iná aplikácia, takže „teraz nie“ nepôjde. Umlčať ma vieš zastavením v páse hore — tým však prestanem aj merať.', 'Another app holds {combo}, so “not now” won’t work. You can still stop me in the top bar — but then I stop measuring too.'),
    'log.snooze_started': _sk_en(
        'Teraz nie: {minutes} minút sa neozvem. Sledovanie to nezastaví.',
        'Not now: I won’t speak up for {minutes} minutes. It doesn’t stop watching.'),
    'log.snooze_ended': _sk_en('Stíšenie skončilo', 'Snooze ended'),
    'log.snooze_cancelled': _sk_en('Stíšenie zrušené', 'Snooze cancelled'),
})


# --- Charts on the Today and History pages --------------------------------
# The session trace, time split across zones, the deviation on cards,
# axes and the day grid. The tone is the same as elsewhere: what we see,
# not what it says about you.
STRINGS.update({
    'dnes.trace_title': _sk_en('Stopa relácie', 'Session trace'),
    'dnes.trace_meta': _sk_en(
        '{time} · pripomienky {n}×',
        '{time} · cues {n}x'),
    'dnes.zones_title': _sk_en(
        'Kde bol dnes tep',
        'Where the session went'),
    'dnes.zones_hint': _sk_en(
        'Koľko z relácie bol tvoj tep v ktorom pásme. Pásma sa merajú voči '
        'tvojej vlastnej pokojovej základni, nie voči tabuľkovej hodnote.',
        'How much of the session you spent in each zone. Zones are measured '
        'against your own resting baseline, not against a chart value.'),

    # Short on purpose: the card is about 200 px wide and a longer sentence
    # was cut off mid-word in it. How many sessions the average is from is
    # also shown by the micro-chart next to the number.
    # NOTE: here were 'dashboard.delta_up/down/same' - the sentence about the
    # deviation under the number on a card ("▲ 3 oproti priemeru z 8", ▲ 3
    # vs the average of 8). They left with the micro-chart; the reason is in
    # app.py at `_dashboard_stat_value`.

    # --- the Sound page (rebuilt on SettingRow) ----------------------------
    # Names without a colon: in a settings row the name stands above the
    # explanation, not before the field. The explanations are the main
    # thing - the original page was the only one in the app that did not
    # have a single sentence by its controls.
    # The panel is not called "Voice": a row in it is also called "Voice"
    # and a heading identical to the item under it reads as a typo.
    'settings.audio_voice_title': _sk_en(
        'Hlas pripomienok',
        'Cue voice'),
    'settings.audio_volume_title': _sk_en('Hlasitosť', 'Loudness'),
    'settings.volume': _sk_en('Hlasitosť', 'Volume'),
    'settings.volume_sub': _sk_en(
        'Platí len pre pripomienky. Hlasitosť hry sa tým nemení.',
        'Applies to cues only. Game volume is not affected.'),
    'settings.balance': _sk_en('Pomer zvuk ↔ hlas', 'Sound ↔ voice mix'),
    'settings.balance_sub': _sk_en(
        'Ako sa hlasitosť rozdelí medzi zvukový efekt a hlas. Vľavo vedie zvuk, vpravo hlas.',
        'How the volume splits between the sound effect and the voice. Left favours the sound, right favours the voice.'),
    'settings.engine': _sk_en(
        'Zdroj hlasu',
        'Voice source'),
    'settings.engine_sub': _sk_en(
        'Prirodzený hlas znie lepšie, ale texty pripomienok (nikdy nie tep) posiela na prevod službe Microsoft — len keď nesledujem. Hlas z Windows nič neposiela.',
        'The natural voice sounds better, but it sends the text of your cues (never your heart rate) to Microsoft to be turned into speech — only while I’m not watching. The Windows voice sends nothing.'),
    'settings.voice': _sk_en('Hlas', 'Voice'),
    # While listening the app does not go to Microsoft (`_speak_text`): a
    # missing cue is spoken with the Windows voice and prepared only after
    # `stop_listening`.
    'log.edge_not_cached_later': _sk_en(
        'Táto pripomienka ešte nemá pripravený prirodzený hlas — tentoraz hovorím hlasom z Windows. Počas sledovania ho nepripravujem; pripravím ho, keď sledovanie zastavíš.',
        'This cue’s natural voice isn’t ready yet — speaking with the Windows voice this time. I don’t prepare it while watching; I’ll do it when you stop watching.'),
    # The same for the whole preparation (`pregenerate`): the auto-profile
    # at game start, a profile switch or a voice change while listening are
    # postponed until after the game.
    'edge.after_game': _sk_en(
        'Hlas pripomienok pripravím, keď zastavíš sledovanie.',
        'I’ll prepare the cue voice when you stop watching.'),
    'settings.voice_sub': _sk_en(
        'Pre každú pripomienku bez vlastného hlasu.',
        'For every cue without a voice of its own.'),
    'settings.rate': _sk_en('Rýchlosť reči', 'Speech speed'),
    'settings.rate_sub': _sk_en(
        'Mínus spomaľuje, plus zrýchľuje. V strese sa pomalšia reč lepšie vníma.',
        'Minus slows it down, plus speeds it up. Slower speech is easier to follow under stress.'),
    'settings.preview': _sk_en('Ako to znie', 'How it sounds'),
    'settings.preview_sub': _sk_en(
        'Prehrá prvú pripomienku presne tak, ako zaznie v hre — s týmto hlasom, hlasitosťou aj pomerom.',
        'Plays the first cue exactly as it will sound in-game — with this voice, volume and mix.'),
    'settings.preview_btn': _sk_en('Vyskúšať', 'Try it'),
    # Words by the speech-rate slider: "-4" alone does not say whether
    # that is a lot.
    'settings.speed_slow': _sk_en('pomaly', 'slow'),
    'settings.speed_normal': _sk_en('normálne', 'normal'),
    'settings.speed_fast': _sk_en('rýchlo', 'fast'),
    'settings.audio_reset': _sk_en('Vrátiť odporúčané', 'Restore recommended'),
    'settings.audio_reset_sub': _sk_en(
        'Hlasitosť, pomer aj rýchlosť reči sa vrátia na '
        'hodnoty, s ktorými appka prišla. Vybraný hlas ostane.',
        'Volume, mix and speech speed go back to the values the '
        'app shipped with. Your chosen voice stays.'),
    'settings.audio_reset_btn': _sk_en('Vrátiť', 'Restore'),
    # --- session export to a spreadsheet ----------------------------------
    'history.export_btn': _sk_en('Exportovať do tabuľky', 'Export to a spreadsheet'),
    'history.export_filetype': _sk_en('Tabuľka pre Excel (CSV)', 'Excel spreadsheet (CSV)'),
    'history.export_local': _sk_en(
        'Tep ani relácie nikam neposielam — sú len v tvojom počítači a súbor '
        'si uložíš, kam chceš.',
        'I send your heart rate and sessions nowhere — they stay on this '
        'computer, and you choose where the file goes.'),
    'history.export_empty': _sk_en('Zatiaľ nie je čo exportovať — najprv odohraj reláciu so senzorom tepu.',
                                   'Nothing to export yet — play a session with the heart rate sensor first.'),
    'history.export_extra': _sk_en('Popri tom sa uložilo:\n{files}',
                                   'Alongside it, these were saved:\n{files}'),
    'history.export_col.longest_above_s': _sk_en('najdlhšie nad prahom (s)',
                                                 'longest stretch above (s)'),
    'history.export_col.above_runs': _sk_en('úseky nad prahom', 'runs above'),
    'history.export_col.cancelled_dip': _sk_en('zrušené poklesom', 'cancelled by dip'),
    'history.export_col.cancelled_gap': _sk_en('zrušené výpadkom', 'cancelled by dropout'),
    'history.export_col.hold_s': _sk_en('potrebné držanie (s)', 'required hold (s)'),
    'history.export_col.context': _sk_en('kontext', 'context'),
    'history.export_done': _sk_en('Uložených {n} relácií do {path}.',
                                  'Saved {n} sessions to {path}.'),
    'history.export_failed': _sk_en('Export sa nepodaril: {err}', 'Export failed: {err}'),
    'log.sessions_exported': _sk_en('Export: {n} relácií do tabuľky',
                                    'Export: {n} sessions to a spreadsheet'),
    # column names in the table
    'history.export_col.date': _sk_en('Dátum', 'Date'),
    'history.export_col.start': _sk_en('Začiatok', 'Start'),
    'history.export_col.duration_min': _sk_en('Dĺžka (min)', 'Length (min)'),
    'history.export_col.avg_bpm': _sk_en('Priemerný tep', 'Average BPM'),
    'history.export_col.min_bpm': _sk_en('Najnižší tep', 'Lowest BPM'),
    'history.export_col.max_bpm': _sk_en('Najvyšší tep', 'Highest BPM'),
    'history.export_col.baseline_bpm': _sk_en('Pokojová základňa', 'Resting baseline'),
    'history.export_col.over_min': _sk_en('Nad hranicou (min)', 'Over limit (min)'),
    # The column key 'breathing' (hr_stats.CSV_COLUMNS) stays because of the
    # data; the content is auto_triggers = all automatic cues, not just breath.
    'history.export_col.breathing': _sk_en(
        'Pripomienky od appky',
        'Cues from the app'),
    'history.export_col.peak_stress': _sk_en('Špička záťaže', 'Peak load'),
    'history.export_col.hrr_bpm': _sk_en('Zotavenie (HRR)', 'Recovery (HRR)'),
    'history.export_col.hrpi': _sk_en(
        'Výdrž tepu (HRPI)',
        'HR persistence (HRPI)'),
    'history.export_col.calm_min': _sk_en('Pokoj (min)', 'Calm (min)'),
    'history.export_col.raised_min': _sk_en('Zvýšená (min)', 'Raised (min)'),
    'history.export_col.high_min': _sk_en('Vysoká (min)', 'High (min)'),
    'history.export_col.critical_min': _sk_en('Špička (min)', 'Peak (min)'),
    # 0.2: signal coverage (hr_stats.pokrytie_signalu)
    'history.export_col.signal': _sk_en('signál %', 'signal %'),
    # 0.2: session world, heart rate dropouts, blind time and pauses in
    # input - at the end
    'history.export_col.world': _sk_en('svet', 'world'),
    'history.export_col.dropouts': _sk_en('výpadky tepu', 'heart-rate dropouts'),
    'history.export_col.blind_s': _sk_en('bez signálu (s)', 'without signal (s)'),
    'history.export_col.pause_episodes': _sk_en('pauzy vo vstupe', 'input pauses'),

    # reassurance about local data - in the onboarding too, right by the
    # anti-cheat
    'ob.step2.tag_local': _sk_en(
        'Tep aj relácie zostávajú v tvojom počítači — a kedykoľvek si ich '
        'vyexportuješ do tabuľky',
        'Heart rate and sessions stay on your computer — and you can export '
        'them to a spreadsheet any time'),

    # --- tour: the heart rate half of the app + continuing ----------------
    'tour.sensor.title': _sk_en('Hodinky a tep', 'Watch and heart rate'),
    'tour.sensor.body': _sk_en(
        'Tu prijímam tvoj tep z telefónu. Keď ho mám, ozvem sa sama, keď ti záťaž chvíľu drží hore — nemusíš si na to v zápale hry spomenúť ty. Bez hodiniek mlčím.',
        'This is where I receive your heart rate from the phone. Once I have it, I speak up on my own when your load holds up for a while — you don’t have to remember it mid-game. Without a watch I stay silent.'),
    'tour.sensor.pair': {
        'sk': 'Spárovať hodinky',
        'en': 'Pair your watch',
        'ja': '時計をつなぐ',
        'zh': '连接手表',
        'ru': 'Подключить часы',
        'es': 'Vincular el reloj',
        'de': 'Uhr verbinden',
        'fr': 'Connecter la montre',
        'pt': 'Parear o relógio',
    },
    'tour.history.title': _sk_en('História relácií', 'Session history'),
    'tour.history.body': _sk_en(
        'Po pár reláciách tu uvidíš vývoj — pokojovú základňu, zotavenie tepu '
        'aj mriežku dní s reláciou. Kliknutím na riadok si ktorúkoľvek reláciu '
        'pozrieš zblízka.',
        'After a few sessions you will see the trend here — resting baseline, '
        'heart rate recovery and a grid of the days you played. Click a row to '
        'look at any session up close.'),
    'settings.tour_row_at': _sk_en('Prehliadka appky — krok {n} z {total}',
                                   'App tour — step {n} of {total}'),
    'settings.tour_resume': _sk_en('Pokračovať', 'Continue'),

    # --- QR for the phone app ---------------------------------------------
    # The code is hidden behind a mark by default (a white square in a dark
    # panel screams, and whoever already has the app does not want to see
    # it) - so the labels are for the switch, not for the picture.
    'hr.qr_show': _sk_en('Naskenovať telefónom', 'Scan with your phone'),
    'hr.qr_hide': _sk_en('Skryť kódy', 'Hide the codes'),
    'hr.qr_android': _sk_en(
        'Android / Wear OS\n„HeartRateOnStream for OBS“ (zdarma).\nAdresu a port nájdeš v „Ako spárovať hodinky…“.',
        'Android / Wear OS\n"HeartRateOnStream for OBS" (free).\nThe address and port are in “How to pair your watch…”.'),
    # iPhone (0.2): the path is in the code, but untested - the author has
    # no Apple device and PulseOSC is paid. A player must not buy it on the
    # strength of a sentence nobody has verified.
    'hr.qr_ios': _sk_en(
        'iPhone / Apple Watch\n„PulseOSC“ (platená).\nZatiaľ nevyskúšané.\nAdresu a port nájdeš v „Ako spárovať hodinky…“.',
        'iPhone / Apple Watch\n"PulseOSC" (paid).\nNot tested yet.\nThe address and port are in “How to pair your watch…”.'),
    # Last line of both QR descriptions IN the pairing guide ITSELF
    # (`ui_dialogs._qr_popis`): a link to "How to pair your watch…" would
    # point there to the button that opened this window.
    'hr.qr_addr_above': _sk_en(
        'Adresu a port nájdeš v rámiku hore.',
        'The address and port are in the box above.'),
    # The original text promised "HeartRateOnStream (Google Play / App
    # Store)" - but that app is not on the App Store and on iPhone no app
    # speaks the obs-websocket protocol. iOS needs OSC (PulseOSC).
    'hr.step2_body': _sk_en(
        'Android / Wear OS: „HeartRateOnStream for OBS“ z Google Play (zdarma). iPhone / Apple Watch: „PulseOSC“ z App Store (platená, zatiaľ nevyskúšaná — autor nemá Apple). Adresu a port (krok 3) zadáš v oboch appkách. Heslo, scéna a zdroj platia len pre appku na Androide — na iPhone krok 4 preskoč. Naskenuj kód nižšie a prepoj appku s hodinkami.',
        'Android / Wear OS: “HeartRateOnStream for OBS” from Google Play (free). iPhone / Apple Watch: “PulseOSC” from the App Store (paid, untested so far — the author has no Apple device). Both apps need the address and port (step 3). The password, scene and source apply to the Android app only — on an iPhone, skip step 4. Scan a code below and connect the app to your watch.'),

    # --- onboarding: fixes to the first four steps ------------------------
    # A fourth pictogram (the app installs FOUR triggers, the step showed
    # three), a sentence about the mechanism (nowhere in the introduction
    # did it say that it depends on keys the player presses anyway) and a CTA
    # that did not promise getting into the game.
    'ob.step1.cap_release': _sk_en(
        'Pusti stisk',
        'Loosen your grip'),
    # 0.2 (stress-gate): "at the next break" no longer applies - the
    # translations that promised it are gone (they are filled in in the
    # language phase).
    'ob.step1.how': _sk_en(
        'Nemusíš nič stláčať ani si nič pamätať — appka sleduje tvoju záťaž a ozve sa sama v krátkej pauze, keď už záťaž nestúpa. Kým je tvoj tep v pásme Špička, radšej mlčí.',
        'You do not have to press or remember anything — the app watches your load and speaks up by itself in a break, once the load has stopped climbing. While your pulse is in the peak zone, it stays quiet.'),
    'onboarding.confirm': _sk_en('Hotovo — spustiť', 'Done — start'),
    'ob.step3.later_note': _sk_en(
        'Nechceš teraz? Klikni Ďalej — spárovať môžeš kedykoľvek cez „{page} → Ako spárovať hodinky…“.',
        'Later? Just hit Next — you can pair any time under “{page} → How to pair your watch…”.'),

    'log.audio_reset': _sk_en('Zvuk vrátený na odporúčané hodnoty',
                              'Sound restored to recommended values'),

    'history.pick_metric': _sk_en('Metrika', 'Metric'),
    'history.pick_period': _sk_en('Obdobie', 'Period'),
    'history.band_label': _sk_en('tvoje bežné rozpätie', 'your usual range'),
    'history.unit.baseline': _sk_en('BPM', 'BPM'),
    'history.unit.hrr': _sk_en('BPM za minútu', 'BPM per minute'),
    'history.unit.over': _sk_en('minúty', 'minutes'),
    'history.unit.peak': _sk_en('z 0–100', 'of 0-100'),
    # 0.2: a chart point is the average PER SESSION on the given day / month
    'history.unit.session_len': _sk_en('minúty na reláciu', 'minutes per session'),
    'history.unit.calm_time': _sk_en('minúty na reláciu', 'minutes per session'),
    'history.unit.signal': _sk_en('% času s tepom', '% of the time with a pulse'),
    'history.unit.breath': _sk_en('priemer na reláciu', 'average per session'),

    # 0.2: the heading does not claim that a cue "works" - the chart is only
    # the shift of heart rate after a cue and the hint below it says it is
    # not proof.
    'history.effect_title': _sk_en(
        'Ako sa hýbal tep po pripomienke',
        'How your pulse moved after a cue'),
    # 0.2 (ladder + gate): a cue comes only when load is not rising, so the
    # drop after it is partly built in - the sentence has to say so. The old
    # _tr7 translation was deleted, so that the old wording does not survive in
    # any language.
    'history.effect_hint': _sk_en(
        'Posun tepu po pripomienke, ktorá zaznela (len hra). Vľavo od stredu znamená, že tep klesol — ale tep klesá aj sám a pripomienka teraz chodí, až keď záťaž už nestúpa, takže pokles po nej nie je dôkaz, že zabrala. Tenká čiarka je rozsah, v ktorom sa skutočná hodnota pravdepodobne nachádza — kým presahuje stred, rozdiel môže byť aj opačný.',
        'How your pulse moved after a cue that made a sound (play only). Left of centre means it dropped — but your pulse also drops on its own, and cues now come only once your load has stopped climbing, so a drop after a cue is no proof it worked. The thin line is the range the true value likely sits in — while it crosses the centre, the difference could go either way.'),
    'history.effect_few': _sk_en('zatiaľ {n} — málo na tvrdenie',
                                 'only {n} so far — too few to say'),
    'history.effect_empty': _sk_en(
        'Zatiaľ nezaznela ani jedna pripomienka, z ktorej by sa dalo merať.',
        'No cue has been delivered yet that could be measured.'),
    'cue.category.grounding': _sk_en('ťažisko', 'grounding'),
    'cue.category.jaw': _sk_en('čeľusť', 'jaw'),
    'cue.category.release': _sk_en(
        'ruka a pohľad',
        'grip & gaze'),
    'cue.category.breath': _sk_en('dych', 'breath'),
    'history.rhythm_title': _sk_en('Pravidelnosť', 'Consistency'),
    # The number of days, NOT an unbroken streak. The streak was dropped
    # from the app on purpose: it is the only element that can be broken,
    # and the app is meant to calm. This number says the same thing ("you
    # keep coming back to it"), but nothing in it can be lost by one
    # skipped evening.
    # {weeks} = how many weeks the grid shows (at most 26, 0.3 batch 4) -
    # the number of days is from the same weeks, not from the whole year.
    'history.days_played': _sk_en('Dní s reláciou · {weeks} týž.',
                                  'Days with a session · {weeks} wk'),
    'history.grid_less': _sk_en('menej', 'less'),
    'history.grid_more': _sk_en('viac', 'more'),

    'history.detail_title': _sk_en('Relácia zblízka', 'One session up close'),
    'history.detail_peak': _sk_en('Najvyšší tep', 'Highest heart rate'),
    'history.detail_hrr': _sk_en('Zotavenie', 'Recovery'),
    'history.detail_breath': _sk_en(
        'Pripomienky',
        'Cues'),
    'history.detail_hrpi': _sk_en(
        'Výdrž',
        'Persistence'),
    # 0.2: the detail shows all values of the session; the other labels are
    # words from the table (history.col_*)
    'history.detail_calm': _sk_en('V pokoji', 'In calm'),
    'history.detail_signal': _sk_en('Signál', 'Signal'),
    'history.detail_felt': _sk_en('Cítené · merané', 'Felt · measured'),
    'history.detail_hint': _sk_en('Klikni na riadok v tabuľke a pozrieš si inú reláciu.',
                                  'Click a row in the table to look at another session.'),
    'history.detail_empty': _sk_en('Zatiaľ žiadna relácia — tu sa objaví jej krivka.',
                                   'No session yet — its curve will show up here.'),
    'history.detail_no_curve': _sk_en(
        'Táto relácia je zo staršej verzie, tvar krivky sa už dopočítať nedá. '
        'Nové relácie si ho ukladajú.',
        'This session comes from an older version, so its curve cannot be '
        'reconstructed. New sessions store it.'),
})


# ==========================================================================
# TRANSLATION into ja / zh / ru / es / de / fr / pt
# ==========================================================================
#
# Keys defined via `_sk_en()` have the other seven languages temporarily
# in English. Here they are filled in - `_tr7` overwrites only those
# seven and leaves sk/en alone, so the source wording is not duplicated
# and cannot drift apart.
#
# NOTE: the translations are machine-made (Claude). For a wide release,
# especially the content in `guide.*` (biomechanics and breathing
# techniques, where the precision of the wording really matters), we
# recommend having them reviewed by native speakers.

def _tr7(key, ja, zh, ru, es, de, fr, pt):
    """Adds seven languages to a key that already has sk and en."""
    entry = STRINGS.get(key)
    if entry is None:
        return
    entry.update({"ja": ja, "zh": zh, "ru": ru, "es": es, "de": de,
                  "fr": fr, "pt": pt})

# --- batch 1: navigation, dock, onboarding, triggers ----------------------
# "alpha" is kept in its English form in the other languages too - it is
# an established label for a stage, not a word to translate.
_tr7('app.version_short', 'alpha 0.3.1', 'alpha 0.3.1', 'alpha 0.3.1', 'alpha 0.3.1', 'Alpha 0.3.1', 'alpha 0.3.1', 'alpha 0.3.1')
_tr7('common.open', '開く', '打开', 'Открыть', 'Abrir', 'Öffnen', 'Ouvrir', 'Abrir')
_tr7('dock.pulse_live_tip', '心拍を受信中', '正在接收心率', 'Пульс поступает', 'Pulso en directo', 'Puls kommt an', 'Le pouls arrive', 'Pulso ao vivo')
_tr7('dock.start', '▶ 見守りを開始', '▶ 开始关注', '▶ Начать наблюдение', '▶ Empezar a observar', '▶ Beobachtung starten', '▶ Lancer l’observation', '▶ Começar a observar')
_tr7('dock.stop', '■ 見守りを停止', '■ 停止关注', '■ Остановить наблюдение', '■ Dejar de observar', '■ Beobachtung stoppen', '■ Arrêter l’observation', '■ Parar de observar')
_tr7('dock.stop_tip', '見守りを停止 — 再び開始するまで合図は出しません。', '停止关注——在你重新开始前，我不会出声。', 'Остановить наблюдение — я молчу, пока не запустишь меня снова.', 'Deja de observar: no aviso hasta que me vuelvas a iniciar.', 'Beobachtung stoppen — ich melde mich nicht, bis du mich wieder startest.', 'Arrêter l’observation — je ne me manifeste plus jusqu’à ce que tu me relances.', 'Parar de observar — não aviso até você me iniciar de novo.')
_tr7('engine.edge', '自然な音声（オンライン、Microsoft）', '自然语音（联网，Microsoft）', 'Естественный (онлайн, Microsoft)', 'Natural (en línea, Microsoft)', 'Natürlich (online, Microsoft)', 'Naturelle (en ligne, Microsoft)', 'Natural (online, Microsoft)')
_tr7('engine.sapi', 'Windows（オフライン）', 'Windows（离线）', 'Windows (без интернета)', 'Windows (sin conexión)', 'Windows (ohne Internet)', 'Windows (hors ligne)', 'Windows (sem internet)')
_tr7('kamae.running', '見守り中', '关注中', 'Наблюдаю', 'Observando', 'Ich beobachte', 'J’observe', 'Observando')
_tr7('kamae.running_sub', '心拍を見ながら、いい頃合いを待っています。', '正在关注心率，等待合适的时机。', 'Слежу за пульсом и жду подходящий момент.', 'Vigilo tu pulso y espero el momento adecuado.', 'Ich beobachte deinen Puls und warte auf den richtigen Moment.', 'Je surveille ton pouls et j’attends le bon moment.', 'Acompanho o seu pulso e espero o momento certo.')
_tr7('sidebar.state_tip', '緑の丸 — 見守り中。三角 — 見守り中ですが、時計からの心拍が途切れました。輪の中のこはく色の点 — 「今はいい」、合図は出しません。中が空の輪 — 停止中。「今日」ページの ▶ で開始できます。', '实心绿点——我在关注。三角形——我在关注，但手表的心率中断了。圆圈里的琥珀色点——“现在不要”，我不会出声。空心圆圈——我已停止；在「今天」页面点 ▶ 即可开始。', 'Сплошная зелёная точка — я наблюдаю. Треугольник — я наблюдаю, но пульс с часов пропал. Янтарная точка в кольце — «не сейчас», я не подам голос. Пустой кружок — я остановлена; запусти меня кнопкой ▶ на странице «Сегодня».', 'Punto verde relleno: estoy observando. Triángulo: estoy observando, pero se cortó el pulso del reloj. Punto ámbar en un anillo: «ahora no», no aviso. Círculo vacío: estoy detenida; me inicias con ▶ en la página Hoy.', 'Grüner Punkt — ich beobachte. Dreieck — ich beobachte, aber der Puls von der Uhr ist ausgefallen. Bernsteinfarbener Punkt im Ring — „Jetzt nicht“, ich melde mich nicht. Leerer Ring — ich bin gestoppt; starte mich mit ▶ auf der Seite Heute.', 'Point vert plein — j’observe. Triangle — j’observe, mais le pouls de la montre s’est interrompu. Point ambre dans un anneau — « pas maintenant », je ne me manifeste pas. Cercle vide — je suis arrêtée ; lance-moi avec ▶ sur la page Aujourd’hui.', 'Ponto verde cheio — estou observando. Triângulo — estou observando, mas o pulso do relógio caiu. Ponto âmbar num anel — “agora não”, não vou avisar. Círculo vazio — estou parada; você me inicia com ▶ na página Hoje.')
_tr7('kamae.armed', '構えました', '已蓄势', 'Наготове', 'Preparada', 'Bereit', 'Prête', 'Pronta')
_tr7('kamae.armed_sub', '体がしばらく上がっています。いい頃合いを待ちます。', '你的身体已经紧绷了一阵子。我会等一个合适的时机。', 'Тело уже какое-то время на взводе. Подожду подходящий момент.', 'Llevas un rato con el cuerpo tenso. Esperaré un buen momento.', 'Dein Körper ist schon eine Weile oben. Ich warte auf einen guten Moment.', 'Ton corps est tendu depuis un moment. J’attendrai le bon moment.', 'O seu corpo está em tensão há algum tempo. Vou esperar um bom momento.')
_tr7('dnes.lastcue', '最後に話したのは {min} 分前 · {label}', '上次开口是 {min} 分钟前 · {label}', 'В последний раз — {min} мин назад · {label}', 'Habló por última vez hace {min} min · {label}', 'Zuletzt vor {min} Min · {label}', 'Dernière fois il y a {min} min · {label}', 'Falou pela última vez há {min} min · {label}')
_tr7('dnes.lastcue_now', 'たった今話しました · {label}', '刚刚开口 · {label}', 'Только что · {label}', 'Acaba de hablar · {label}', 'Gerade eben · {label}', 'À l’instant · {label}', 'Acabou de falar · {label}')
_tr7('kamae.stopped', '停止中', '已停止', 'Остановлено', 'Detenido', 'Gestoppt', 'Arrêté', 'Parado')
_tr7('kamae.stopped_sub', 'セッションは記録せず、合図も出しません。上のボタンで開始できます。', '我不保存记录，也不会出声。用上面的按钮启动我。', 'Не записываю сессию и не подаю знаков. Запусти меня кнопкой сверху.', 'No grabo la sesión ni aviso. Iníciame con el botón de arriba.', 'Ich zeichne keine Sitzung auf und melde mich nicht. Starte mich mit dem Knopf oben.', 'Je n’enregistre pas de séance et je ne me manifeste pas. Lance-moi avec le bouton ci-dessus.', 'Não gravo a sessão nem aviso. Você me inicia com o botão acima.')
_tr7('mode.combo', '音声＋効果音', '语音 + 音效', 'Голос + звук', 'Voz + sonido', 'Stimme + Ton', 'Voix + son', 'Voz + som')
_tr7('mode.sfx', '効果音', '音效', 'Звук', 'Sonido', 'Ton', 'Son', 'Som')
_tr7('mode.tts', '音声', '语音', 'Голос', 'Voz', 'Stimme', 'Voix', 'Voz')
_tr7('nav.dnes', '今日', '今天', 'Сегодня', 'Hoy', 'Heute', "Aujourd'hui", 'Hoje')
_tr7('nav.historia', '履歴', '历史', 'История', 'Historial', 'Verlauf', 'Historique', 'Histórico')
_tr7('nav.nastavenia_tabs.spustace', '合図', '提示', 'Подсказки', 'Avisos', 'Hinweise', 'Rappels', 'Avisos')
_tr7('nav.nastavenia_tabs.vseobecne', '全般', '通用', 'Общие', 'General', 'Allgemein', 'Général', 'Geral')
_tr7('nav.nastavenia_tabs.zvuk', 'サウンド', '声音', 'Звук', 'Sonido', 'Ton', 'Son', 'Som')
_tr7('nav.spustace', '合図', '提示', 'Подсказки', 'Avisos', 'Hinweise', 'Rappels', 'Avisos')
_tr7('nav.vhre', '時計とゲーム中', '手表与游戏中', 'Часы и в игре', 'Reloj y en el juego', 'Uhr und im Spiel', 'Montre et en jeu', 'Relógio e no jogo')
_tr7('nav.zvuk', 'サウンド / オーディオ', '声音 / 音频', 'Звук / Аудио', 'Sonido / Audio', 'Ton / Audio', 'Son / Audio', 'Som / Áudio')
_tr7('ob.back', '戻る', '返回', 'Назад', 'Atrás', 'Zurück', 'Retour', 'Voltar')
_tr7('ob.next', '次へ', '下一步', 'Далее', 'Siguiente', 'Weiter', 'Suivant', 'Próximo')
_tr7('ob.skip', '時計へスキップ', '跳到手表', 'Сразу к часам', 'Saltar al reloj', 'Weiter zur Uhr', 'Passer à la montre', 'Pular para o relógio')
_tr7('ob.step1.title', 'ゲーム中にアプリが思い出させてくれること', '游戏中，应用会提醒你这些', 'Вот о чём приложение напомнит тебе в игре', 'Esto es lo que la app te recuerda en plena partida', 'Daran erinnert dich die App mitten im Spiel', 'Voici ce que l’app te rappelle en pleine partie', 'É disso que o app te lembra no meio do jogo')
_tr7('ob.step1.cap_grounding', '重心を落として', '沉下重心', 'Опусти вес', 'Baja el peso', 'Gewicht senken', 'Relâche ton poids', 'Baixa o peso')
_tr7('ob.step1.cap_jaw', '顎をゆるめて', '松开下巴', 'Разожми челюсть', 'Afloja la mandíbula', 'Kiefer lockern', 'Desserre la mâchoire', 'Solta o maxilar')
_tr7('ob.step1.cap_release', '握りをゆるめて', '松开握力', 'Ослабь хват', 'Afloja la mano', 'Griff lockern', 'Relâche ta prise', 'Solta a mão')
_tr7('ob.step1.cap_breath', '吐いて', '呼气', 'Выдохни', 'Espira', 'Ausatmen', 'Expire', 'Expira')
_tr7('ob.step2.title', '控えめに。画面の中央を避けて。', '低调。避开屏幕中央。', 'Незаметно. В стороне от центра экрана.', 'Discreto. Lejos del centro de la pantalla.', 'Unaufdringlich. Weg von der Bildschirmmitte.', 'Discret. Loin du centre de l’écran.', 'Discreto. Longe do centro da tela.')
_tr7('ob.step2.body', '画像は画面の中央を避けて現れ、また消えます。クリックは画像を通り抜けてゲームに届きます。位置は「{page}」ページの「表示」で動かせます。', '图片会出现在避开屏幕中央的位置，然后再消失。点击会穿过它直达游戏。可以在“{page}”页面用“显示”来移动它。', 'Картинка появляется в стороне от центра экрана и снова исчезает. Клики проходят сквозь неё в игру. Переместить её можно на странице «{page}» кнопкой «Показать».', 'La imagen aparece lejos del centro de la pantalla y vuelve a desaparecer. Los clics la atraviesan y llegan al juego. La mueves en la página «{page}» con «Mostrar».', 'Das Bild erscheint abseits der Bildschirmmitte und verschwindet wieder. Klicks gehen durch es hindurch ins Spiel. Verschieben kannst du es auf der Seite „{page}“ mit „Zeigen“.', 'L’image apparaît loin du centre de l’écran, puis disparaît. Les clics la traversent jusqu’au jeu. Tu la déplaces sur la page « {page} » avec « Afficher ».', 'A imagem aparece longe do centro da tela e some de novo. Os cliques passam por ela até o jogo. Você a move na página “{page}” com “Mostrar”.')
_tr7('ob.step2.tag_local', '心拍もセッションもこのPCに残る — いつでも表に書き出せる', '心率和记录都留在你的电脑里——随时可以导出成表格', 'Пульс и сессии остаются на твоём компьютере — и в любой момент их можно выгрузить в таблицу', 'El pulso y las sesiones se quedan en tu ordenador, y puedes exportarlos a una hoja de cálculo cuando quieras', 'Puls und Sitzungen bleiben auf deinem Rechner — und du kannst sie jederzeit als Tabelle exportieren', 'Le pouls et les séances restent sur ton ordinateur — et tu peux les exporter en tableur quand tu veux', 'O pulso e as sessões ficam no seu computador — e você pode exportá-los para uma planilha quando quiser')
_tr7('ob.step3.pair_now', '今すぐ時計をつなぐ', '现在连接手表', 'Подключить часы сейчас', 'Vincular un reloj ahora', 'Jetzt eine Uhr verbinden', 'Connecter une montre maintenant', 'Parear um relógio agora')
_tr7('ob.step3.later_note', '今はやめておく？「次へ」を押して — 「{page} → 時計のつなぎ方…」からいつでもつなげます。', '现在不想？点“下一步”——随时可以在“{page} → 如何连接手表…”里连接。', 'Не сейчас? Нажми «Далее» — подключить часы можно в любой момент через «{page} → Как подключить часы…».', '¿Más tarde? Pulsa Siguiente: puedes vincularlo cuando quieras en «{page} → Cómo vincular tu reloj…».', 'Später? Klick einfach auf Weiter — verbinden kannst du jederzeit unter „{page} → Uhr verbinden…“.', 'Plus tard ? Clique sur Suivant — tu peux connecter ta montre à tout moment via « {page} → Comment connecter ta montre… ».', 'Depois? Clique em Próximo — você pode parear a qualquer momento em “{page} → Como parear o seu relógio…”.')
_tr7('onboarding.confirm', '完了 — 開始', '完成——开始', 'Готово — запустить', 'Listo: empezar', 'Fertig — starten', 'Terminé — démarrer', 'Pronto — iniciar')
_tr7('slot.file_short', 'ファイル', '文件', 'Файл', 'Archivo', 'Datei', 'Fichier', 'Arquivo')
_tr7('slot.record_short', '録音', '录音', 'Запись', 'Grabar', 'Aufnehmen', 'Enregistrer', 'Gravar')
_tr7('slots.title', '私が話すこと', '我会说什么', 'Что я скажу', 'Qué digo', 'Was ich sage', 'Ce que je dis', 'O que eu digo')
_tr7('slots.clear_selection', '選択を解除', '取消选择', 'Снять выделение', 'Quitar selección', 'Auswahl aufheben', 'Annuler la sélection', 'Limpar seleção')
_tr7('slots.remove_selected', '選択したものを削除', '删除所选', 'Удалить выбранные', 'Eliminar seleccionados', 'Ausgewählte entfernen', 'Supprimer la sélection', 'Remover selecionados')
_tr7('slots.selected_count', '選択中: {n}', '已选：{n}', 'Выбрано: {n}', 'Seleccionados: {n}', 'Ausgewählt: {n}', 'Sélectionnés : {n}', 'Selecionados: {n}')
_tr7('slots.remove_confirm', '選択した {n} 個の合図を削除しますか？\n\n{list}', '删除所选的 {n} 条提示？\n\n{list}', 'Удалить выбранные подсказки ({n})?\n\n{list}', '¿Eliminar los {n} avisos seleccionados?\n\n{list}', '{n} ausgewählte Hinweise entfernen?\n\n{list}', 'Supprimer les {n} rappels sélectionnés ?\n\n{list}', 'Remover os {n} avisos selecionados?\n\n{list}')
_tr7('dashboard.stats_title', 'マイ統計', '我的统计', 'Моя статистика', 'Mis estadísticas', 'Meine Statistiken', 'Mes statistiques', 'Minhas estatísticas')
_tr7('dashboard.edit_stats', '✎ 編集', '✎ 编辑', '✎ изменить', '✎ editar', '✎ bearbeiten', '✎ modifier', '✎ editar')
_tr7('dashboard.picker_title', '表示したいもの', '你想看到什么', 'Что показывать', 'Qué quieres ver', 'Was du sehen willst', 'Ce que tu veux voir', 'O que você quer ver')
_tr7('dashboard.unit.hrr', '1分あたりの BPM', '每分钟 BPM', 'BPM за минуту', 'BPM por minuto', 'BPM pro Minute', 'BPM par minute', 'BPM por minuto')
_tr7('dashboard.unit.over', 'このセッション', '本次记录', 'за эту сессию', 'esta sesión', 'diese Sitzung', 'cette séance', 'esta sessão')
_tr7('dashboard.unit.avg', 'このセッション', '本次记录', 'за эту сессию', 'esta sesión', 'diese Sitzung', 'cette séance', 'esta sessão')
_tr7('dashboard.unit.breath', '自動', '自动', 'автоматически', 'automático', 'automatisch', 'automatique', 'automático')
_tr7('dashboard.unit.max', 'このセッション', '本次记录', 'за эту сессию', 'esta sesión', 'diese Sitzung', 'cette séance', 'esta sessão')
_tr7('dashboard.unit.peak', '0〜100 のうち', '满分 100', 'из 0–100', 'de 0–100', 'von 0–100', 'sur 0–100', 'de 0–100')
_tr7('dnes.hr_title', '心拍と負荷', '心率与负荷', 'Пульс и нагрузка', 'Pulso y carga', 'Puls und Last', 'Pouls et charge', 'Pulso e carga')
_tr7('dnes.bpm_unit', '1分あたりの拍数', '每分钟心跳', 'ударов в минуту', 'latidos por minuto', 'Schläge pro Minute', 'battements par minute', 'batimentos por minuto')
_tr7('dnes.hr_connected', '電話と接続済み', '手机已连接', 'телефон подключён', 'móvil conectado', 'Handy verbunden', 'téléphone connecté', 'celular conectado')
_tr7('dnes.hr_waiting', '時計を待っています', '等待手表', 'жду часы', 'esperando al reloj', 'warte auf die Uhr', 'en attente de la montre', 'aguardando o relógio')
_tr7('dnes.empty_btn', '時計をつなぐ', '连接手表', 'Подключить часы', 'Vincular el reloj', 'Uhr verbinden', 'Connecter la montre', 'Parear o relógio')
_tr7('dnes.trace_title', 'セッションの軌跡', '本次轨迹', 'След сессии', 'Rastro de la sesión', 'Spur der Sitzung', 'Trace de la séance', 'Rastro da sessão')
_tr7('dnes.zones_title', 'セッションの内訳', '这次都在哪个区间', 'Где прошла сессия', 'Dónde fue la sesión', 'Wo die Sitzung lag', 'Où la séance s’est passée', 'Onde a sessão passou')
_tr7('dnes.zones_hint', 'セッションのうち、どの帯にどれだけいたか。帯は自分の安静時ベースラインを基準に測る — 表の数値ではない。', '本次记录中你在各区间待了多久。区间以你自己的静息基线为准，而不是表格数值。', 'Сколько времени за сессию пульс был в каждой зоне. Зоны считаются от твоей собственной базовой линии покоя, а не от табличного значения.', 'Cuánto de la sesión pasaste en cada zona. Las zonas se miden frente a tu propia línea base en reposo, no frente a un valor de tabla.', 'Wie viel der Sitzung du in welcher Zone verbracht hast. Die Zonen messen gegen deine eigene Ruhebasislinie, nicht gegen einen Tabellenwert.', 'Combien de la séance tu as passé dans chaque zone. Les zones se mesurent par rapport à ta propre ligne de base au repos, pas à une valeur de table.', 'Quanto da sessão você passou em cada zona. As zonas são medidas em relação à sua própria linha de base em repouso, não a um valor de tabela.')
_tr7('dnes.why_line', 'ゲーム中、気づく前に体はこわばる — Zanshin はそこに短いリセットを結びつける。', '游戏中身体在你察觉前就绷紧了——Zanshin 把一次短暂的重置绑在那一刻。', 'В игре тело напрягается раньше, чем ты заметишь, — Zanshin привязывает к этому короткий сброс.', 'En plena partida el cuerpo se tensa antes de que lo notes: Zanshin ata un reinicio corto a ese momento.', 'Mitten im Spiel verspannt sich der Körper, bevor du es merkst — Zanshin knüpft daran einen kurzen Reset.', 'En pleine partie, le corps se crispe avant que tu le remarques — Zanshin y attache une remise à zéro courte.', 'No meio do jogo, o corpo trava antes de você perceber — o Zanshin associa a isso um reset curto.')
_tr7('tour.next', '次へ', '下一步', 'Далее', 'Siguiente', 'Weiter', 'Suivant', 'Próximo')
_tr7('tour.skip', 'スキップ', '跳过', 'Пропустить', 'Saltar', 'Überspringen', 'Passer', 'Pular')
_tr7('tour.done_btn', 'わかった', '知道了', 'Понятно', 'Entendido', 'Alles klar', 'Compris', 'Entendido')
_tr7('tour.step_of', 'ステップ {n} / {total}', '第 {n} 步，共 {total} 步', 'ШАГ {n} из {total}', 'PASO {n} de {total}', 'SCHRITT {n} von {total}', 'ÉTAPE {n} sur {total}', 'PASSO {n} de {total}')
_tr7('tour.welcome.title', 'かんたんツアー', '快速导览', 'Быстрая экскурсия', 'Recorrido rápido', 'Kurze Tour', 'Visite rapide', 'Visita rápida')
_tr7('tour.welcome.body', 'アプリの中の5か所を案内します — 1分ほどです。いつでもスキップできます。', '带你看看应用里的五个地方——大约一分钟。随时可以跳过。', 'Покажу пять мест в приложении — примерно минута. Пропустить можно в любой момент.', 'Te enseño cinco lugares de la app: cerca de un minuto. Puedes saltarlo cuando quieras.', 'Ich zeige dir fünf Stellen in der App — etwa eine Minute. Du kannst jederzeit überspringen.', 'Je te montre cinq endroits de l’app — environ une minute. Tu peux passer à tout moment.', 'Vou te mostrar cinco lugares do app — cerca de um minuto. Você pode pular quando quiser.')
_tr7('tour.triggers.title', '合図', '提示', 'Подсказки', 'Avisos', 'Hinweise', 'Rappels', 'Avisos')
_tr7('tour.sensor.title', '時計と心拍', '手表与心率', 'Часы и пульс', 'Reloj y pulso', 'Uhr und Puls', 'Montre et pouls', 'Relógio e pulso')
_tr7('tour.history.title', 'セッション履歴', '记录历史', 'История сессий', 'Historial de sesiones', 'Sitzungsverlauf', 'Historique des séances', 'Histórico de sessões')
_tr7('tour.history.body', '何回かセッションを重ねると、ここに推移が出る — 安静時ベースライン、心拍回復、そして遊んだ日のグリッド。行をクリックすれば、どのセッションもじっくり見られる。', '几次记录之后，这里会显示趋势——静息基线、心率恢复，以及你游玩日期的格子图。点击某一行就能细看那一次。', 'После нескольких сессий здесь появится динамика — базовая линия покоя, восстановление пульса и сетка дней с сессиями. Клик по строке открывает любую сессию вблизи.', 'Tras unas cuantas sesiones verás aquí la evolución: línea base en reposo, recuperación del pulso y una cuadrícula de los días que jugaste. Haz clic en una fila para ver cualquier sesión de cerca.', 'Nach ein paar Sitzungen siehst du hier den Verlauf — Ruhebasislinie, Herzfrequenz-Erholung und ein Raster der Tage, an denen du gespielt hast. Ein Klick auf eine Zeile zeigt jede Sitzung aus der Nähe.', 'Après quelques séances, tu verras ici l’évolution — ligne de base au repos, récupération cardiaque et une grille des jours joués. Clique sur une ligne pour voir une séance de près.', 'Depois de algumas sessões, você vê aqui a evolução — linha de base em repouso, recuperação do pulso e uma grade dos dias em que jogou. Clique numa linha para ver qualquer sessão de perto.')
_tr7('tour.dock.title', '円相（ensō）— アプリの状態', '圆相（ensō）——应用的状态', 'Энсо — состояние приложения', 'El ensō: el estado de la app', 'Das Ensō — der Zustand der App', 'L’ensō — l’état de l’app', 'O ensō — o estado do app')
_tr7('tour.done.title', 'これで終わり', '就这些', 'Вот и всё', 'Eso es todo', 'Das war’s', 'C’est tout', 'É tudo')
_tr7('tour.dock.body', 'これは円相（ensō）、アプリの印です。見守っている間はゆっくり呼吸し、止まっているときは動きません。内側のゆっくりした環は、いい頃合いを待っている合図です。クリックすると開始・停止できます。状態は左上の点でもわかります。', '这是圆相（ensō），应用的标志。我在关注时，它会缓慢呼吸；停下时，它静止不动。内部缓慢的环表示我在等待合适的时机。点击它即可开始或停止。左上角的圆点也会显示状态。', 'Это энсо, знак приложения. Пока я слежу, оно медленно дышит; когда я остановлена, оно неподвижно. Медленное кольцо внутри значит, что я жду подходящего момента. Щёлкни по нему, чтобы запустить или остановить меня. Состояние показывает и точка слева вверху.', 'Esto es el ensō, la marca de la app. Mientras observo, respira despacio; cuando estoy detenida, se queda quieto. Un anillo lento por dentro significa que espero un buen momento. Haz clic en él para iniciarme o detenerme. El punto de arriba a la izquierda también muestra el estado.', 'Das ist das Ensō, das Zeichen der App. Solange ich aufpasse, atmet es langsam; wenn ich gestoppt bin, steht es still. Ein langsamer Ring darin heißt, dass ich auf einen guten Moment warte. Klick darauf, um mich zu starten oder zu stoppen. Den Zustand zeigt auch der Punkt oben links.', 'Voici l’ensō, la marque de l’app. Quand je veille, il respire lentement ; quand je suis arrêtée, il reste immobile. Un anneau lent à l’intérieur signifie que j’attends le bon moment. Clique dessus pour me démarrer ou m’arrêter. Le point en haut à gauche montre aussi l’état.', 'Este é o ensō, a marca do app. Enquanto estou de olho, ele respira devagar; quando estou parada, fica imóvel. Um anel lento por dentro quer dizer que estou esperando um bom momento. Clique nele para me iniciar ou parar. O ponto no canto superior esquerdo também mostra o estado.')
_tr7('tour.done.body', 'このツアーは設定からいつでもやり直せる。よいゲームを。', '这个导览随时可以在设置里重看。玩得开心。', 'Эту экскурсию можно повторить в настройках когда угодно. Хорошей игры.', 'Puedes repetir este recorrido cuando quieras en Ajustes. Que disfrutes la partida.', 'Diese Tour kannst du jederzeit in den Einstellungen wiederholen. Viel Spaß beim Spielen.', 'Tu peux rejouer cette visite à tout moment dans les réglages. Bon jeu.', 'Você pode repetir esta visita quando quiser em Configurações. Bom jogo.')
_tr7('metric.bpm.short', '今、心臓が1分間に何回打っているか。', '你的心脏此刻每分钟跳多少下。', 'Сколько раз в минуту сейчас бьётся твоё сердце.', 'Cuántas veces por minuto late ahora tu corazón.', 'Wie oft dein Herz gerade pro Minute schlägt.', 'Combien de fois par minute ton cœur bat en ce moment.', 'Quantas vezes por minuto o seu coração bate agora.')
_tr7('metric.bpm.more', '基本の数字。それ自体はあまり語らない — 大事なのは安静時の水準からどれだけ動くか、そして落ち着いたときにどれだけ速く下がるか。', '最基础的数字。单看它意义不大——重要的是它相对你的静息水平怎么动，以及你平静下来时下降得多快。', 'Базовое число. Само по себе оно мало что говорит — важно, как оно движется относительно твоего уровня покоя и как быстро падает, когда ты успокаиваешься.', 'El número base. Por sí solo dice poco: lo que importa es cómo se mueve frente a tu nivel de reposo y con qué rapidez baja cuando te calmas.', 'Die Grundzahl. Für sich allein sagt sie wenig — entscheidend ist, wie sie sich gegenüber deinem Ruheniveau bewegt und wie schnell sie fällt, wenn du runterkommst.', 'Le chiffre de base. Seul, il dit peu — ce qui compte, c’est comment il bouge par rapport à ton niveau de repos et à quelle vitesse il redescend quand tu te calmes.', 'O número básico. Sozinho diz pouco — o que importa é como ele se move em relação ao seu nível de repouso e com que rapidez desce quando você se acalma.')
_tr7('metric.baseline.tag', '安静時心拍', '静息心率', 'пульс в покое', 'pulso en reposo', 'Ruhepuls', 'pouls au repos', 'pulso em repouso')
_tr7('metric.hrr.tag', '回復', '恢复', 'восстановление', 'recuperación', 'Erholung', 'récupération', 'recuperação')
_tr7('metric.over.tag', '心拍上限超え', '超过心率上限', 'выше границы пульса', 'sobre el límite de pulso', 'über Pulsgrenze', 'au-dessus de la limite', 'acima do limite de pulso')
_tr7('metric.avg.tag', '平均', '平均', 'средний', 'media', 'Schnitt', 'moyenne', 'média')
_tr7('metric.max.tag', '最高', '最高', 'максимум', 'máximo', 'Maximum', 'maximum', 'máximo')
_tr7('metric.peak.tag', '負荷ピーク', '负荷峰值', 'пик нагрузки', 'pico de carga', 'Last-Spitze', 'pic de charge', 'pico de carga')
_tr7('metric.week.tag', '今週', '本周', 'за неделю', 'esta semana', 'diese Woche', 'cette semaine', 'esta semana')
_tr7('metric.baseline.title', '安静時ベースライン', '静息基线', 'Базовая линия покоя', 'Línea base en reposo', 'Ruhebasislinie', 'Ligne de base au repos', 'Linha de base em repouso')
_tr7('metric.baseline.short', '安静時の心拍 — 何にも追われていないとき。', '静息时的心率——没有任何事催着你的时候。', 'Твой пульс в покое — когда тебя ничто не гонит.', 'Tu pulso en reposo: cuando nada te está exigiendo.', 'Dein Puls in Ruhe — wenn dich nichts antreibt.', 'Ton pouls au repos — quand rien ne te pousse.', 'O seu pulso em repouso — quando nada te pressiona.')
_tr7('metric.baseline.more', '私は最も落ち着いた瞬間から算出する。日ごとに上がっていくなら、体が疲れているかストレスがあるのかもしれない — 必ずしもゲームのせいではない（睡眠、カフェイン、体調）。だから一つの数字ではなく、時間の流れで追う。', '我从你最平静的时刻推算。如果它一天天升高，可能是身体疲惫或压力大——不一定是游戏造成的（睡眠、咖啡因、生病）。所以我看的是长期走势，而不是单个数字。', 'Я вывожу её из твоих самых спокойных моментов. Если она растёт день за днём, тело может быть уставшим или в стрессе — не обязательно из-за игры (сон, кофеин, болезнь). Поэтому я слежу за ней во времени, а не по одному числу.', 'La deduzco de tus momentos más tranquilos. Si sube día tras día, tu cuerpo puede estar cansado o estresado, no necesariamente por jugar (sueño, cafeína, enfermedad). Por eso la sigo en el tiempo y no como un número suelto.', 'Ich leite sie aus deinen ruhigsten Momenten ab. Steigt sie Tag für Tag, ist dein Körper vielleicht müde oder gestresst — nicht zwangsläufig vom Spielen (Schlaf, Koffein, Krankheit). Deshalb verfolge ich sie über die Zeit, nicht als Einzelwert.', 'Je la déduis de tes moments les plus calmes. Si elle monte jour après jour, ton corps est peut-être fatigué ou stressé — pas forcément à cause du jeu (sommeil, caféine, maladie). C’est pourquoi je la suis dans le temps, pas comme un chiffre isolé.', 'Eu a deduzo dos seus momentos mais calmos. Se ela sobe dia após dia, o corpo pode estar cansado ou estressado — não necessariamente por causa do jogo (sono, cafeína, doença). Por isso eu a acompanho ao longo do tempo, não como um número isolado.')
_tr7('metric.hrr.title', '心拍回復', '心率恢复', 'Восстановление пульса', 'Recuperación del pulso', 'Herzfrequenz-Erholung', 'Récupération cardiaque', 'Recuperação do pulso')
_tr7('metric.hrr.short', '心拍が跳ね上がったあと、1分でどれだけ下がったか。', '心率飙升之后，一分钟内下降了多少。', 'На сколько упал пульс за минуту после скачка.', 'Cuánto bajó tu pulso en el minuto siguiente a un pico.', 'Um wie viel dein Puls in der Minute nach einem Ausschlag gefallen ist.', 'De combien ton pouls est redescendu dans la minute suivant un pic.', 'Quanto o seu pulso desceu no minuto seguinte a um pico.')
_tr7('metric.zones.title', '心拍上限超えと帯ごとの時間', '超过心率上限的时间与各区间时间', 'Время выше границы пульса и по зонам', 'Tiempo sobre el límite de pulso y por zonas', 'Zeit über der Pulsgrenze und in Zonen', 'Temps au-dessus de la limite cardiaque et par zones', 'Tempo acima do limite de pulso e por zonas')
_tr7('metric.zones.short', 'セッションのうち、心拍が高いまま過ごした割合。', '本次记录里你心率偏高的时间占多少。', 'Сколько времени за сессию пульс был высоким.', 'Cuánto de la sesión pasaste con el pulso alto.', 'Wie viel der Sitzung du mit hohem Puls verbracht hast.', 'Combien de la séance tu as passé avec un pouls élevé.', 'Quanto da sessão você passou com o pulso alto.')
_tr7('metric.zones.calm', '平静', '平静', 'покой', 'calma', 'ruhig', 'calme', 'calmo')
_tr7('metric.zones.raised', 'やや上昇', '略高', 'повышенная', 'elevada', 'erhöht', 'élevée', 'elevada')
_tr7('metric.zones.high', '高い', '偏高', 'высокая', 'alta', 'hoch', 'haute', 'alta')
_tr7('metric.zones.critical', 'ピーク', '高峰', 'пик', 'pico', 'Spitze', 'pic', 'pico')
_tr7('metric.hrpi.title', '心拍の持続', '心率持续', 'Устойчивость пульса', 'Persistencia del pulso', 'Puls-Persistenz', 'Persistance du pouls', 'Persistência do pulso')
_tr7('metric.hrpi.short', '心拍がどれだけ高く、どれだけ長く続いたかを一つにまとめた数字。', '把心率有多高、持续多久合成一个数字。', 'Одно число, связывающее, насколько высоко и как долго шёл твой пульс.', 'Un número que une lo alto y lo largo que estuvo tu pulso.', 'Eine Zahl, die verbindet, wie hoch und wie lange dein Puls lief.', 'Un chiffre qui relie la hauteur et la durée de ton pouls.', 'Um número que junta o quão alto e por quanto tempo o seu pulso esteve.')
_tr7('metric.hrpi.more', '例：101 = 心拍が毎分 101 拍以上だった時間が、合計で 101 秒以上あったということ。高さと長さを一つにまとめるので、二つのセッションを一目で比べられます。', '例如 101 = 心率达到每分钟 101 次以上的时间累计至少 101 秒。它把高度和时长合为一体，让你一眼就能比较两次记录。', 'Например, 101 = пульс был не ниже 101 удара в минуту в сумме не меньше 101 секунды. Число соединяет высоту и длительность, так что две сессии можно сравнить одним взглядом.', 'Por ejemplo, 101 = tu pulso estuvo al menos a 101 latidos por minuto durante al menos 101 segundos en total. Une altura y duración, así que puedes comparar dos sesiones de un vistazo.', 'Z. B. 101 = dein Puls lag insgesamt mindestens 101 Sekunden lang bei mindestens 101 Schlägen pro Minute. Er verbindet Höhe und Dauer, sodass du zwei Sitzungen auf einen Blick vergleichen kannst.', 'Par ex. 101 = ton pouls a été d’au moins 101 battements par minute pendant au moins 101 secondes au total. Ce chiffre joint hauteur et durée, si bien que tu compares deux séances d’un coup d’œil.', 'Ex.: 101 = o seu pulso ficou em pelo menos 101 batimentos por minuto durante pelo menos 101 segundos no total. Junta altura e duração, por isso você compara duas sessões num relance.')
_tr7('metric.over.title', '心拍上限を超えた時間', '超过心率上限的时间', 'Время выше границы пульса', 'Tiempo sobre el límite de pulso', 'Zeit über der Pulsgrenze', 'Temps au-dessus de la limite cardiaque', 'Tempo acima do limite de pulso')
_tr7('metric.avg.title', '今日の平均心拍', '今日平均心率', 'Средний пульс сегодня', 'Pulso medio de hoy', 'Durchschnittspuls heute', 'Pouls moyen aujourd’hui', 'Pulso médio hoje')
_tr7('metric.avg.more', 'セッション全体を一つの数字にしたもの — 日々の比較には安静時ベースラインのほうが役に立つ。あちらは最も落ち着いた瞬間だけを数えるから。', '把整场记录压成一个数字——但要做日常比较，静息基线更有用，因为它只统计你最平静的时刻。', 'Одно число на всю сессию — для сравнения день ко дню полезнее базовая линия покоя: она считает только самые спокойные моменты.', 'Un número para toda la sesión: para comparar día a día es más útil la línea base en reposo, porque solo cuenta tus momentos más tranquilos.', 'Eine Zahl für die ganze Sitzung — für den Vergleich von Tag zu Tag ist die Ruhebasislinie nützlicher, denn sie zählt nur deine ruhigsten Momente.', 'Un chiffre pour toute la séance — pour comparer d’un jour à l’autre, la ligne de base au repos est plus utile : elle ne compte que tes moments les plus calmes.', 'Um número para toda a sessão — para comparar dia a dia, a linha de base em repouso é mais útil, porque só conta os seus momentos mais calmos.')
_tr7('metric.max.title', '最高心拍', '最高心率', 'Самый высокий пульс', 'Pulso más alto', 'Höchster Puls', 'Pouls le plus haut', 'Pulso mais alto')
_tr7('metric.max.more', '単発のピークはそれ自体ではあまり語らない — もっと大事なのは、そのあとどれだけ速く心拍が戻ったか（HRR）。', '单个峰值本身说明不了什么——更重要的是之后心率回落得多快（HRR）。', 'Один скачок сам по себе мало что говорит — важнее, как быстро пульс потом вернулся вниз (HRR).', 'Un pico aislado dice poco por sí solo: importa más lo rápido que bajó el pulso después (HRR).', 'Ein einzelner Ausschlag sagt für sich wenig — wichtiger ist, wie schnell der Puls danach wieder gefallen ist (HRR).', 'Un pic isolé dit peu en soi — ce qui compte davantage, c’est la vitesse à laquelle le pouls est redescendu ensuite (HRR).', 'Um pico isolado diz pouco por si — importa mais a rapidez com que o pulso desceu depois (HRR).')
_tr7('metric.peak.title', '負荷のピーク', '负荷峰值', 'Пик нагрузки', 'Pico de carga', 'Last-Spitze', 'Pic de charge', 'Pico de carga')
_tr7('metric.peak.short', '今日のセッション中の最高の負荷値（0〜100）。', '今天记录中的最高负荷值（0–100）。', 'Самое высокое значение нагрузки (0–100) за сегодняшнюю сессию.', 'El valor de carga más alto (0–100) durante la sesión de hoy.', 'Der höchste Lastwert (0–100) in der heutigen Sitzung.', 'La valeur de charge la plus haute (0–100) pendant la séance du jour.', 'O valor de carga mais alto (0–100) durante a sessão de hoje.')
_tr7('metric.peak.more', '負荷は心拍から三つを組み合わせる：安静時からどれだけ上か、どれだけ速く上がっているか、どれだけ長く高いままか。負荷のピークは、その組み合わせが最も高かった一瞬。', '负荷把心率的三件事合起来：比静息高多少、上升多快、在高位停留多久。负荷峰值就是这个组合最高的那一刻。', 'Нагрузка соединяет три вещи из пульса: насколько ты выше покоя, как быстро он растёт и как долго держится. Пик нагрузки — самый высокий момент этого сочетания.', 'La carga combina tres cosas del pulso: cuánto estás por encima del reposo, con qué rapidez sube y cuánto se mantiene. El pico de carga es el momento más alto de esa combinación.', 'Die Last kombiniert drei Dinge aus dem Puls: wie weit über der Ruhe du bist, wie schnell er steigt und wie lange er oben bleibt. Die Last-Spitze ist der höchste Moment dieser Kombination.', 'La charge combine trois éléments du pouls : de combien tu es au-dessus du repos, à quelle vitesse il monte et combien de temps il reste haut. Le pic de charge est le moment le plus haut de cette combinaison.', 'A carga combina três coisas do pulso: quanto você está acima do repouso, com que rapidez sobe e quanto tempo fica alto. O pico de carga é o momento mais alto dessa combinação.')
_tr7('metric.week.title', '今週のセッション', '本周记录数', 'Сессии на этой неделе', 'Sesiones esta semana', 'Sitzungen diese Woche', 'Séances cette semaine', 'Sessões esta semana')
_tr7('insight.need_more', 'これまで {n}/{need} セッション — 3回そろうと、私はそれらを横断して傾向を探しはじめる。', '目前 {n}/{need} 次记录——满三次后，我会开始跨记录寻找规律。', 'Пока {n} из {need} сессий — после трёх я начну искать закономерности между ними.', 'Por ahora {n} de {need} sesiones: a partir de tres, empiezo a buscar patrones entre ellas.', 'Bisher {n} von {need} Sitzungen — ab drei suche ich nach Mustern über sie hinweg.', 'Pour l’instant {n} séances sur {need} — à partir de trois, je commence à chercher des tendances.', 'Até agora {n} de {need} sessões — a partir de três, começo a procurar padrões entre elas.')
_tr7('log.audio_reset', 'サウンドを推奨値に戻した', '声音已恢复为推荐值', 'Звук возвращён к рекомендуемым значениям', 'Sonido restaurado a los valores recomendados', 'Ton auf empfohlene Werte zurückgesetzt', 'Son remis aux valeurs recommandées', 'Som restaurado para os valores recomendados')
_tr7('log.sessions_exported', 'エクスポート：{n} セッションを表に', '导出：{n} 次记录到表格', 'Экспорт: {n} сессий в таблицу', 'Exportación: {n} sesiones a una hoja de cálculo', 'Export: {n} Sitzungen in eine Tabelle', 'Export : {n} séances vers un tableur', 'Exportação: {n} sessões para uma planilha')
_tr7('log.slots_removed_bulk', '{n} 個の合図を削除しました。', '已删除 {n} 条提示。', 'Удалено подсказок: {n}.', 'Se eliminaron {n} avisos.', '{n} Hinweise entfernt.', '{n} rappels supprimés.', 'Removidos {n} avisos.')
_tr7('log.hotkey_on', 'ショートカット {combo} が有効 — 30分間静かにします', '快捷键 {combo} 已就绪——会让我安静半小时', 'Сочетание {combo} готово — заглушит меня на полчаса', 'El atajo {combo} está listo: me silenciará media hora', 'Tastenkürzel {combo} ist bereit — es macht mich eine halbe Stunde still', 'Le raccourci {combo} est prêt — il me fera taire une demi-heure', 'O atalho {combo} está pronto — me silencia por meia hora')
_tr7('log.snooze_ended', 'ミュートが終わった', '静音结束', 'Пауза закончилась', 'La pausa terminó', 'Pause beendet', 'Pause terminée', 'A pausa terminou')
_tr7('log.snooze_cancelled', 'ミュートを解除した', '已取消静音', 'Пауза отменена', 'Pausa cancelada', 'Pause abgebrochen', 'Pause annulée', 'Pausa cancelada')
_tr7('log.hr_session_saved', 'セッションを保存 — 平均 {avg} BPM、最高 {max} BPM、負荷ピーク {peak}。', '记录已保存——平均 {avg} BPM，最高 {max} BPM，负荷峰值 {peak}。', 'Сессия сохранена — средний {avg} уд/мин, пик {max} уд/мин, пик нагрузки {peak}.', 'Sesión guardada: media {avg} ppm, pico {max} ppm, pico de carga {peak}.', 'Sitzung gespeichert — Schnitt {avg} S/min, Spitze {max} S/min, Last-Spitze {peak}.', 'Séance enregistrée — moyenne {avg} bpm, pic {max} bpm, pic de charge {peak}.', 'Sessão salva — média {avg} bpm, pico {max} bpm, pico de carga {peak}.')
_tr7('log.monitor_target', '画像と心拍パネルは次の画面に描きます：{target}。', '图片和心率面板将显示在：{target}。', 'Картинки и панель пульса будут рисоваться на: {target}.', 'Las imágenes y el panel de pulso se dibujarán en: {target}.', 'Bilder und das Puls-Panel werden jetzt hier gezeichnet: {target}.', 'Les images et le panneau du pouls s’afficheront sur : {target}.', 'As imagens e o painel de pulso serão desenhados em: {target}.')
_tr7('guide.block.physiology', '体で起きていること', '身体里发生了什么', 'Что происходит в теле', 'Qué pasa en tu cuerpo', 'Was im Körper passiert', 'Ce qui se passe dans le corps', 'O que acontece no corpo')
_tr7('guide.block.instruction', 'あなたにできること', '你可以做什么', 'Что ты можешь сделать', 'Qué puedes hacer', 'Was du tun kannst', 'Ce que tu peux faire', 'O que você pode fazer')
_tr7('guide.not_medical_note',
     'これは健康のための一般的なヒントで、医学的な助言ではありません — Zanshin は医療機器ではありません。心臓や呼吸に問題があるなら、まず医師に相談してください。',
     '这些是一般性的健康小贴士，不是医疗建议——Zanshin 不是医疗器械。如果你有心脏或呼吸方面的问题，请先咨询医生。',
     'Это общие советы для самочувствия, а не медицинская рекомендация — Zanshin не является медицинским изделием. Если у тебя проблемы с сердцем или дыханием, сначала посоветуйся с врачом.',
     'Son consejos generales de bienestar, no consejo médico — Zanshin no es un producto sanitario. Si tienes algún problema de corazón o de respiración, consulta antes con un médico.',
     'Das sind allgemeine Tipps fürs Wohlbefinden, kein medizinischer Rat — Zanshin ist kein Medizinprodukt. Wenn du Herz- oder Atembeschwerden hast, sprich zuerst mit einer Ärztin oder einem Arzt.',
     "Ce sont des conseils généraux de bien-être, pas un avis médical — Zanshin n'est pas un dispositif médical. Si tu as un problème cardiaque ou respiratoire, parles-en d'abord à un médecin.",
     'São dicas gerais de bem-estar, não aconselhamento médico — o Zanshin não é um dispositivo médico. Se você tem algum problema cardíaco ou respiratório, fale primeiro com um médico.')
_tr7('hud.section_title', 'ゲーム中の心拍パネル', '游戏中的心率面板', 'Панель пульса в игре', 'Panel de pulso en el juego', 'Puls-Panel im Spiel', 'Panneau de pouls en jeu', 'Painel de pulso no jogo')
_tr7('hud.enable', 'ゲーム中にパネルを表示 — 配信向け', '在游戏中显示面板——用于直播', 'Показывать панель в игре — для стрима', 'Mostrar el panel en el juego — para streaming', 'Panel im Spiel zeigen — fürs Streaming', 'Afficher le panneau en jeu — pour le stream', 'Mostrar o painel no jogo — para stream')
_tr7('hud.hint', '隅に出る小さなパネル：心拍、直近3分、負荷、セッションの進み。配信の視聴者には意味があるけれど、プレイ中のあなたにはむしろ注意を奪うので、オフにしてある。クリックはゲームに通り、Alt+Tab には出ない。', '角落里的小面板：心率、最近 3 分钟、负荷和本次进度。它对直播观众有意义；你自己玩的时候，它更多是在分散注意力，所以默认关闭。点击会穿透到游戏，也不会出现在 Alt+Tab 中。', 'Маленькая панель в углу: пульс, последние 3 минуты, нагрузка и ход сессии. Зрителям стрима она полезна; тебе во время игры она скорее отнимает внимание, поэтому выключена. Клики проходят в игру, в Alt+Tab она не появляется.', 'Un panel pequeño en la esquina: tu pulso, los últimos 3 minutos, la carga y el avance de la sesión. Tiene sentido para quien ve tu stream; a ti, mientras juegas, más bien te quita atención, por eso está desactivado. Los clics pasan al juego y nunca aparece en Alt+Tab.', 'Ein kleines Eckpanel: dein Puls, die letzten 3 Minuten, Last und Sitzungsverlauf. Für Stream-Zuschauer ergibt es Sinn; dich kostet es beim Spielen eher Aufmerksamkeit, deshalb ist es aus. Klicks gehen ans Spiel durch, und es taucht nie im Alt+Tab auf.', 'Un petit panneau dans un coin : ton pouls, les 3 dernières minutes, la charge et l’avancée de la séance. Il a du sens pour les spectateurs du stream ; à toi, pendant que tu joues, il prend plutôt de l’attention, c’est pourquoi il est désactivé. Les clics passent au jeu et il n’apparaît jamais dans l’Alt+Tab.', 'Um painel pequeno no canto: o seu pulso, os últimos 3 minutos, a carga e o avanço da sessão. Faz sentido para quem assiste à sua stream; para você, enquanto joga, ele mais tira atenção, por isso está desligado. Os cliques passam para o jogo e ele nunca aparece no Alt+Tab.')
_tr7('hud.opacity', '不透明度', '不透明度', 'Непрозрачность', 'Opacidad', 'Deckkraft', 'Opacité', 'Opacidade')
_tr7('hud.test', 'HUD を 4 秒表示', '显示 HUD 4 秒', 'Показать HUD на 4 с', 'Mostrar el HUD 4 s', 'HUD 4 s zeigen', 'Afficher le HUD 4 s', 'Mostrar o HUD 4 s')
_tr7('hud.load', '負荷', '负荷', 'НАГРУЗКА', 'CARGA', 'LAST', 'CHARGE', 'CARGA')
_tr7('hud.waiting', 'データ待ち', '等待数据', 'ЖДУ ДАННЫЕ', 'ESPERANDO DATOS', 'WARTE AUF DATEN', 'EN ATTENTE DE DONNÉES', 'AGUARDANDO DADOS')
_tr7('hud.calibrating', 'キャリブレーション中…', '校准中…', 'калибрую…', 'calibrando…', 'kalibriere…', 'calibrage…', 'calibrando…')
_tr7('hud.zone.calm', '平静', '平静', 'Покой', 'Calma', 'Ruhig', 'Calme', 'Calmo')
_tr7('hud.zone.raised', 'やや上昇', '略高', 'Повышенная', 'Elevada', 'Erhöht', 'Élevée', 'Elevada')
_tr7('hud.zone.high', '高い', '偏高', 'Высокая', 'Alta', 'Hoch', 'Haute', 'Alta')
_tr7('hud.zone.critical', 'ピーク', '高峰', 'Пик', 'Pico', 'Spitze', 'Pic', 'Pico')
_tr7('hud.session.triggers', '合図 {n}', '提示 {n}', 'ПОДСКАЗКИ {n}', 'AVISOS {n}', 'HINWEISE {n}', 'RAPPELS {n}', 'AVISOS {n}')
_tr7('hud.session.over', '上限超え {time}', '超过上限 {time}', 'ВЫШЕ ГРАНИЦЫ {time}', 'SOBRE EL LÍMITE {time}', 'ÜBER DER GRENZE {time}', 'AU-DESSUS DE LA LIMITE {time}', 'ACIMA DO LIMITE {time}')
_tr7('hud.trigger_row.toggle', 'ゲーム中にアイコンを表示', '在游戏中显示图标', 'Показывать значки в игре', 'Mostrar iconos en el juego', 'Symbole im Spiel zeigen', 'Afficher les icônes en jeu', 'Mostrar ícones no jogo')
_tr7('hud.trigger_row.color', 'アイコンの色', '图标颜色', 'Цвет значков', 'Color de los iconos', 'Symbolfarbe', 'Couleur des icônes', 'Cor dos ícones')
_tr7('hud.snooze.5min', '5 分', '5 分钟', '5 минут', '5 minutos', '5 Minuten', '5 minutes', '5 minutos')
_tr7('hud.snooze.20min', '20 分', '20 分钟', '20 минут', '20 minutos', '20 Minuten', '20 minutes', '20 minutos')
_tr7('hud.snooze.40min', '40 分', '40 分钟', '40 минут', '40 minutos', '40 Minuten', '40 minutes', '40 minutos')
_tr7('hud.snooze.60min', '60 分', '60 分钟', '60 минут', '60 minutos', '60 Minuten', '60 minutes', '60 minutos')
_tr7('hud.snooze.cancel', 'ミュートを解除', '取消静音', 'Отменить паузу', 'Cancelar la pausa', 'Pause aufheben', 'Annuler la pause', 'Cancelar a pausa')
_tr7('overlay.dialog_title', 'ゲーム中の画像', '游戏中的图片', 'Картинки в игре', 'Imágenes en el juego', 'Bilder im Spiel', 'Images en jeu', 'Imagens no jogo')
_tr7('overlay.caption.grounding', '重心を落として', '沉下重心', 'ОПУСТИ ВЕС', 'BAJA EL PESO', 'GEWICHT SENKEN', 'RELÂCHE TON POIDS', 'BAIXA O PESO')
_tr7('overlay.caption.jaw', '顎をゆるめて', '松开下巴', 'РАЗОЖМИ ЧЕЛЮСТЬ', 'AFLOJA LA MANDÍBULA', 'KIEFER LOCKERN', 'DESSERRE LA MÂCHOIRE', 'SOLTA O MAXILAR')
_tr7('overlay.caption.release', '握りをゆるめて', '松开握力', 'ОСЛАБЬ ХВАТ', 'AFLOJA LA MANO', 'GRIFF LOCKERN', 'RELÂCHE TA PRISE', 'SOLTA A MÃO')
_tr7('overlay.caption.inhale', '吸って', '吸气', 'ВДОХ', 'INSPIRA', 'EINATMEN', 'INSPIRE', 'INSPIRA')
_tr7('overlay.caption.exhale', '吐いて', '呼气', 'ВЫДОХ', 'ESPIRA', 'AUSATMEN', 'EXPIRE', 'EXPIRA')
_tr7('overlay.monitor.label', 'どの画面に描くか', '在哪块屏幕上绘制', 'На каком экране рисовать', 'En qué pantalla dibujar', 'Auf welchem Bildschirm zeichnen', 'Sur quel écran dessiner', 'Em qual tela desenhar')
_tr7('overlay.monitor.pick', '画面', '屏幕', 'Экран', 'Pantalla', 'Bildschirm', 'Écran', 'Tela')
_tr7('overlay.monitor.auto', '自動（ゲームが動いている画面）', '自动（游戏所在的屏幕）', 'Автоматически (где идёт игра)', 'Automático (donde corre el juego)', 'Automatisch (wo das Spiel läuft)', 'Automatique (où tourne le jeu)', 'Automático (onde o jogo está rodando)')
_tr7('overlay.monitor.cursor', 'カーソルのある画面', '光标所在的屏幕', 'Где курсор', 'Donde está el cursor', 'Wo der Cursor ist', 'Où est le curseur', 'Onde está o cursor')
_tr7('overlay.monitor.primary', 'メインモニター', '主显示器', 'Основной монитор', 'Monitor principal', 'Hauptmonitor', 'Moniteur principal', 'Monitor principal')
_tr7('overlay.monitor.hint', '「自動」なら私はアクティブなウィンドウのある画面 — つまり今プレイしている画面 — に描く。', '选“自动”时，我会画在当前活动窗口所在的屏幕上——也就是你正在玩的那块。', 'При «Автоматически» я рисую на том экране, где активное окно, — то есть на том, где ты играешь.', 'Con «Automático» dibujo en la pantalla que tiene la ventana activa, es decir, en la que estás jugando.', 'Bei „Automatisch“ zeichne ich auf dem Bildschirm mit dem aktiven Fenster — also dem, auf dem du spielst.', 'Avec « Automatique », je dessine sur l’écran qui a la fenêtre active — celui sur lequel tu joues.', 'Com “Automático”, eu desenho na tela que tem a janela ativa — aquela em que você está jogando.')
_tr7('overlay.fine_tune', '画像のサイズと位置を微調整…', '微调图片的大小和位置…', 'Точнее настроить размер и положение картинок…', 'Ajustar tamaño y posición de las imágenes…', 'Größe und Position der Bilder feinjustieren…', 'Ajuster la taille et la position des images…', 'Ajustar tamanho e posição das imagens…')
_tr7('overlay.test_done', '完了', '完成', 'Готово', 'Listo', 'Fertig', 'Terminé', 'Pronto')
_tr7('overlay.drag_hint', '「表示」を押すと画像が画面に出ます。好きな場所へドラッグし、もう一度クリックすると位置が保存されます。', '点击“显示”，图片会出现在屏幕上。把它拖到你想要的位置，再点一次即可保存位置。', 'Нажми «Показать» — картинка появится на экране. Перетащи её куда хочешь и нажми ещё раз, чтобы сохранить положение.', 'Pulsa «Mostrar» y la imagen aparece en pantalla. Arrástrala donde quieras y vuelve a pulsar para guardar la posición.', 'Klick auf „Zeigen“ — das Bild erscheint auf dem Bildschirm. Zieh es, wohin du willst, und klick noch einmal, um die Position zu speichern.', 'Clique sur « Afficher » — l’image apparaît à l’écran. Fais-la glisser où tu veux et clique à nouveau pour enregistrer la position.', 'Clique em “Mostrar” — a imagem aparece na tela. Arraste-a para onde quiser e clique de novo para salvar a posição.')
_tr7('overlay.color_title', '画像の色', '图片颜色', 'Цвет картинки', 'Color de la imagen', 'Bildfarbe', 'Couleur de l’image', 'Cor da imagem')
_tr7('overlay.breath_seconds', '呼吸のサイクル（秒）', '呼吸周期（秒）', 'Цикл дыхания (в секундах)', 'Ciclo de respiración (en segundos)', 'Atemzyklus (in Sekunden)', 'Cycle de respiration (en secondes)', 'Ciclo de respiração (em segundos)')
_tr7('overlay.breath_inhale', '吸う長さ（秒）', '吸气时长（秒）', 'Длина вдоха (с)', 'Duración de la inspiración (s)', 'Länge des Einatmens (s)', 'Durée de l’inspiration (s)', 'Duração da inspiração (s)')
_tr7('overlay.breath_exhale', '吐く長さ（秒）', '呼气时长（秒）', 'Длина выдоха (с)', 'Duración de la espiración (s)', 'Länge des Ausatmens (s)', 'Durée de l’expiration (s)', 'Duração da expiração (s)')
_tr7('overlay.high_hr_ring', '心拍が高いときも呼吸の輪', '心率高时也显示呼吸环', 'Кольцо и при высоком пульсе', 'Anillo también con el pulso alto', 'Ring auch bei hohem Puls', 'Anneau aussi quand le pouls est élevé', 'Anel também com o pulso alto')
_tr7('dnes.high_hr_ring_quick', '{bpm} BPM超で呼吸の輪', '心率高于 {bpm} BPM 时显示呼吸环', 'Дыхательное кольцо выше {bpm} BPM', 'Anillo de respiración sobre {bpm} BPM', 'Atemring über {bpm} BPM', 'Anneau de respiration au-dessus de {bpm} BPM', 'Anel de respiração acima de {bpm} BPM')
_tr7('overlay.high_hr_ring_bpm', '{bpm} BPM を超えたら', '高于 {bpm} BPM', 'Выше {bpm} BPM', 'Por encima de {bpm} BPM', 'Über {bpm} BPM', 'Au-dessus de {bpm} BPM', 'Acima de {bpm} BPM')
_tr7('overlay.high_hr_ring_hint', '心拍がこの上限を超えると呼吸の輪が現れ、上限より {margin} BPM 以上下がるまでくり返し呼吸し、そのあと吐き終えてから消えます。その間、ほかの合図は出ません。', '心率超过这个上限时，呼吸环会出现并一直循环呼吸，直到心率比上限低至少 {margin} BPM；然后它在一次呼气后结束。在此期间不会出现其他提示。', 'Дыхательное кольцо появляется, когда пульс превышает эту границу, и дышит по кругу, пока он не опустится хотя бы на {margin} BPM ниже неё; потом оно заканчивается после выдоха. Других подсказок в это время не будет.', 'El anillo de respiración aparece cuando tu pulso supera este límite y sigue respirando hasta que el pulso baje al menos {margin} BPM por debajo; entonces termina tras una espiración. Mientras tanto no llega ningún otro aviso.', 'Der Atemring erscheint, wenn dein Puls diese Grenze überschreitet, und atmet immer weiter, bis dein Puls mindestens {margin} BPM darunter sinkt; dann endet der Ring nach einem Ausatmen. In der Zeit kommt kein anderer Hinweis.', 'L’anneau de respiration apparaît quand ton pouls dépasse cette limite et continue de respirer jusqu’à ce que ton pouls redescende d’au moins {margin} BPM en dessous ; l’anneau s’arrête alors après une expiration. Aucun autre rappel ne vient pendant ce temps.', 'O anel de respiração aparece quando o seu pulso passa deste limite e continua respirando até o pulso cair pelo menos {margin} BPM abaixo dele; então o anel termina depois de uma expiração. Nesse meio-tempo não vem nenhum outro aviso.')
_tr7('hr.pair_button', '時計のつなぎ方…', '如何连接手表…', 'Как подключить часы…', 'Cómo vincular tu reloj…', 'Uhr verbinden…', 'Comment connecter ta montre…', 'Como parear o seu relógio…')
_tr7('hr.pair_title', '時計をつなぐ', '连接你的手表', 'Подключение часов', 'Vincular tu reloj', 'Uhr verbinden', 'Connecter ta montre', 'Parear o seu relógio')
_tr7('hr.pair_intro', '心拍は電話のアプリから PC に送られます。Zanshin はそのアプリに OBS のふりをします — OBS 自体をインストールする必要はありません。', '心率由手机上的应用发送到这台电脑。Zanshin 在它看来就像 OBS——你不需要安装 OBS 本身。', 'Пульс на компьютер отправит приложение на телефоне. Для него Zanshin выглядит как OBS — сам OBS устанавливать не нужно.', 'El pulso te lo manda al PC la app del móvil. Para ella, Zanshin se hace pasar por OBS: no hace falta instalar OBS.', 'Den Puls schickt dir die App auf dem Handy an den PC. Für sie sieht Zanshin wie OBS aus — OBS selbst musst du nicht installieren.', 'C’est l’app du téléphone qui envoie ton pouls au PC. Pour elle, Zanshin se fait passer pour OBS — tu n’as pas besoin d’installer OBS.', 'Quem envia o seu pulso para o PC é o app do celular. Para ele, o Zanshin se passa por OBS — você não precisa instalar o OBS.')
_tr7('hr.pair_this_pc', 'この PC のアドレスとポート — 電話に入力する', '这台电脑的地址和端口——输入到手机里', 'АДРЕС И ПОРТ ЭТОГО ПК — введи их в телефоне', 'DIRECCIÓN Y PUERTO DE ESTE PC: escríbelos en el móvil', 'ADRESSE UND PORT DIESES PCS — im Handy eintragen', 'ADRESSE ET PORT DE CE PC — à saisir sur le téléphone', 'ENDEREÇO E PORTA DESTE PC — digite-os no celular')
_tr7('hr.pair_ip_unknown', 'IP を検出できなかった', '无法检测到 IP', 'Не удалось определить IP', 'No se pudo detectar la IP', 'IP konnte nicht erkannt werden', 'Impossible de détecter l’IP', 'Não foi possível detectar o IP')
_tr7('hr.pair_ip_help', 'コマンドプロンプトを開いて ipconfig と入力 — 「IPv4 アドレス」を探す（たいてい 192.168.x.x）。電話と PC は同じ Wi‑Fi にいる必要がある。', '打开命令提示符输入 ipconfig——找到 “IPv4 地址”（通常是 192.168.x.x）。手机和电脑必须在同一个 Wi‑Fi 上。', 'Открой командную строку и набери ipconfig — найди «IPv4-адрес» (обычно 192.168.x.x). Телефон и ПК должны быть в одном Wi‑Fi.', 'Abre el símbolo del sistema y escribe ipconfig: busca «Dirección IPv4» (suele ser 192.168.x.x). El móvil y el PC deben estar en el mismo Wi‑Fi.', 'Öffne die Eingabeaufforderung und tippe ipconfig — such nach „IPv4-Adresse“ (meist 192.168.x.x). Handy und PC müssen im selben WLAN sein.', 'Ouvre l’invite de commandes et tape ipconfig — cherche « Adresse IPv4 » (souvent 192.168.x.x). Le téléphone et le PC doivent être sur le même Wi‑Fi.', 'Abra o Prompt de Comando e digite ipconfig — procure “Endereço IPv4” (normalmente 192.168.x.x). O celular e o PC precisam estar no mesmo Wi‑Fi.')
_tr7('hr.pair_other_ips', 'この PC の他のアドレス（最初のが効かない場合）：{ips}', '这台电脑的其他地址（如果第一个不行）：{ips}', 'Другие адреса этого ПК (если первый не работает): {ips}', 'Otras direcciones de este PC (si la primera no funciona): {ips}', 'Weitere Adressen dieses PCs (falls die erste nicht geht): {ips}', 'Autres adresses de ce PC (si la première ne marche pas) : {ips}', 'Outros endereços deste PC (se o primeiro não funcionar): {ips}')
_tr7('hr.pair_ip_note', '設定では 0.0.0.0 のままにする — この番号は電話に入れるためだけのもの。', '设置里保持 0.0.0.0——这个号码只用来填进手机。', 'В настройках оставь 0.0.0.0 — это число идёт только в телефон.', 'Deja 0.0.0.0 en los ajustes: este número solo se escribe en el móvil.', 'Lass in den Einstellungen 0.0.0.0 — diese Zahl kommt nur ins Handy.', 'Laisse 0.0.0.0 dans les réglages — ce numéro ne sert qu’au téléphone.', 'Deixe 0.0.0.0 nas configurações — este número vai só para o celular.')
_tr7('hr.step1_title', '同じ Wi‑Fi とネットワークの許可', '同一个 Wi‑Fi 和网络许可', 'Один Wi‑Fi и доступ к сети', 'El mismo Wi‑Fi y permiso de red', 'Dasselbe WLAN und Netzwerkzugriff', 'Le même Wi‑Fi et l’accès réseau', 'O mesmo Wi‑Fi e a permissão de rede')
_tr7('hr.step1_body', '電話と PC を同じ Wi‑Fi に（モバイル通信ではなく）。Windows が Zanshin のネットワーク接続を許可するか尋ねてくることがある — プライベート（自宅）ネットワークだけ許可して。', '手机和电脑连在同一个 Wi‑Fi 上（不是移动数据）。Windows 现在可能会询问是否允许 Zanshin 访问网络——只允许专用（家庭）网络。', 'Телефон и ПК — в одном Wi‑Fi (не мобильный интернет). Windows сейчас может спросить, пускать ли Zanshin в сеть, — разреши только частные (домашние) сети.', 'El móvil y el PC en el mismo Wi‑Fi (no datos móviles). Windows puede preguntar ahora si deja entrar a Zanshin en la red: permite solo redes privadas (de casa).', 'Handy und PC im selben WLAN (keine mobilen Daten). Windows fragt jetzt vielleicht, ob Zanshin ins Netzwerk darf — erlaube nur private (Heim-)Netzwerke.', 'Le téléphone et le PC sur le même Wi‑Fi (pas en données mobiles). Windows peut maintenant demander s’il faut autoriser Zanshin sur le réseau — n’autorise que les réseaux privés (domestiques).', 'Celular e PC no mesmo Wi‑Fi (não nos dados móveis). O Windows pode perguntar agora se deve liberar o Zanshin na rede — libere só redes privadas (de casa).')
_tr7('hr.step2_title', '電話にアプリを入れる', '安装手机应用', 'Установи приложение на телефон', 'Instala la app del móvil', 'Handy-App installieren', 'Installe l’app du téléphone', 'Instale o app no celular')
_tr7('hr.step3_title', 'アドレスとポートを入れる', '输入地址和端口', 'Введи адрес и порт', 'Escribe la dirección y el puerto', 'Adresse und Port eintragen', 'Saisis l’adresse et le port', 'Digite o endereço e a porta')
_tr7('hr.step3_body', '電話のアプリに、上の枠のアドレスとポートを入力する。パスワードは空のままでいい。', '在手机应用里填入上方框里的地址和端口。密码留空。', 'В приложении на телефоне введи адрес и порт из рамки выше. Пароль оставь пустым.', 'En la app del móvil introduce la dirección y el puerto del recuadro de arriba. Deja la contraseña vacía.', 'Trag in der Handy-App die Adresse und den Port aus dem Feld oben ein. Das Passwort bleibt leer.', 'Dans l’app du téléphone, saisis l’adresse et le port du cadre ci-dessus. Laisse le mot de passe vide.', 'No app do celular, digite o endereço e a porta do quadro acima. Deixe a senha em branco.')
_tr7('hr.step4_title', 'シーンとソースを選ぶ', '选择场景和来源', 'Выбери сцену и источник', 'Elige la escena y la fuente', 'Szene und Quelle wählen', 'Choisis la scène et la source', 'Escolha a cena e a fonte')
_tr7('hr.step4_body', 'つながったら、シーン「Zanshin」とソース「Tep」を選ぶ。歩数と速度も送れるなら、ソース「Kroky」と「Rychlost」もある。', '连接之后，选择场景 “Zanshin” 和来源 “Tep”。如果还能发送步数和速度，那里也有来源 “Kroky” 和 “Rychlost”。', 'После подключения выбери сцену «Zanshin» и источник «Tep». Если можешь отправлять ещё шаги и скорость, там есть и источники «Kroky» и «Rychlost».', 'Una vez conectado, elige la escena «Zanshin» y la fuente «Tep». Si también puedes enviar pasos y velocidad, ahí están además las fuentes «Kroky» y «Rychlost».', 'Sobald verbunden, wähle die Szene „Zanshin“ und die Quelle „Tep“. Wenn du auch Schritte und Tempo senden kannst, gibt es dort außerdem die Quellen „Kroky“ und „Rychlost“.', 'Une fois connecté, choisis la scène « Zanshin » et la source « Tep ». Si tu peux aussi envoyer les pas et la vitesse, les sources « Kroky » et « Rychlost » sont là aussi.', 'Depois de conectado, escolha a cena “Zanshin” e a fonte “Tep”. Se você também puder enviar passos e velocidade, as fontes “Kroky” e “Rychlost” também estão lá.')
_tr7('hr.step5_title', 'アドレスの下の状態を確認', '查看地址下方的状态', 'Проверь состояние под адресом', 'Mira el estado bajo la dirección', 'Prüf den Status unter der Adresse', 'Vérifie l’état sous l’adresse', 'Confira o status abaixo do endereço')
_tr7('hr.step5_body', 'このガイドを開いた時点で心拍の受信はオンになっている — 何も切り替えなくていい。アドレスの下に BPM で心拍が出たら完了。', '打开这个指南时，心率接收就已经打开了——不用再切换任何东西。地址下方显示出以 BPM 计的心率，就完成了。', 'Это руководство при открытии уже включило приём пульса — ничего переключать не нужно. Когда под адресом появится пульс в BPM, всё готово.', 'Al abrir esta guía se activó la recepción del pulso: no hace falta cambiar nada. Cuando veas tu pulso en BPM bajo la dirección, ya está.', 'Mit dem Öffnen dieser Anleitung ist der Pulsempfang eingeschaltet — du musst nichts umschalten. Sobald du unter der Adresse deinen Puls in BPM siehst, ist alles fertig.', 'En ouvrant ce guide, tu as activé la réception du pouls — rien à basculer. Quand tu vois ton pouls en BPM sous l’adresse, c’est bon.', 'Ao abrir este guia, o recebimento do pulso foi ligado — não precisa mudar nada. Quando aparecer seu pulso em BPM abaixo do endereço, está pronto.')
_tr7('hr.trouble_title', '時計はつながるのに心拍が来ない？', '手表连上了却没有心率？', 'Часы подключаются, а пульса нет?', '¿El reloj conecta pero no llega el pulso?', 'Uhr verbindet sich, aber kein Puls?', 'La montre se connecte mais pas de pouls ?', 'O relógio conecta, mas o pulso não chega?')
_tr7('hr.noconnect_title', '時計がまったくつながらない？', '手表完全连不上？', 'Часы вообще не подключаются?', '¿El reloj no conecta en absoluto?', 'Uhr verbindet sich gar nicht?', 'La montre ne se connecte pas du tout ?', 'O relógio não conecta de jeito nenhum?')
_tr7('hr.noconnect_body', '1) 電話と PC を同じ Wi‑Fi に — モバイル通信、ゲスト用ネットワーク、VPN は不可。\n2) 電話に入れたアドレスが上のものと同じであること — ルーターを再起動すると変わる。\n3) 設定 → ネットワークとインターネット → Wi‑Fi（またはイーサネット）→ 使っているネットワーク → ネットワーク プロファイルの種類：プライベート ネットワーク。\n4) Windows セキュリティ → ファイアウォールとネットワーク保護 → ファイアウォールによるアプリケーションの許可 → 設定の変更 → Zanshin の「プライベート」にチェック。', '1) 手机和电脑连在同一个 Wi‑Fi 上——不能是移动数据、访客网络或 VPN。\n2) 手机里的地址必须和上面的一致——路由器重启后它会变。\n3) 设置 → 网络和 Internet → Wi‑Fi（或以太网）→ 你的网络 → 网络配置文件类型：专用网络。\n4) Windows 安全中心 → 防火墙和网络保护 → 允许应用通过防火墙 → 更改设置 → 勾选 Zanshin 的“专用”。', '1) Телефон и ПК — в одном Wi‑Fi: не мобильный интернет, не гостевая сеть и не VPN.\n2) Адрес в телефоне должен совпадать с адресом выше — после перезапуска роутера он меняется.\n3) Параметры → Сеть и Интернет → Wi‑Fi (или Ethernet) → твоя сеть → Тип сетевого профиля: Частная сеть.\n4) Безопасность Windows → Брандмауэр и защита сети → Разрешить работу с приложением через брандмауэр → Изменить параметры → у Zanshin отметь «Частная».', '1) El móvil y el PC en el mismo Wi‑Fi: ni datos móviles, ni red de invitados, ni VPN.\n2) La dirección del móvil debe coincidir con la de arriba: cambia al reiniciar el router.\n3) Configuración → Red e Internet → Wi‑Fi (o Ethernet) → tu red → Tipo de perfil de red: Red privada.\n4) Seguridad de Windows → Firewall y protección de red → Permitir una aplicación a través del firewall → Cambiar la configuración → marca «Privada» en Zanshin.', '1) Handy und PC im selben WLAN — keine mobilen Daten, kein Gastnetz und kein VPN.\n2) Die Adresse im Handy muss mit der oben übereinstimmen — nach einem Router-Neustart ändert sie sich.\n3) Einstellungen → Netzwerk und Internet → WLAN (oder Ethernet) → dein Netzwerk → Netzwerkprofiltyp: Privates Netzwerk.\n4) Windows-Sicherheit → Firewall- & Netzwerkschutz → Zugriff von App durch Firewall zulassen → Einstellungen ändern → bei Zanshin „Privat“ anhaken.', '1) Le téléphone et le PC sur le même Wi‑Fi — pas de données mobiles, de réseau invité ni de VPN.\n2) L’adresse dans le téléphone doit correspondre à celle du haut — elle change après un redémarrage de la box.\n3) Paramètres → Réseau et Internet → Wi‑Fi (ou Ethernet) → ton réseau → Type de profil réseau : Réseau privé.\n4) Sécurité Windows → Pare-feu et protection du réseau → Autoriser une application via le pare-feu → Modifier les paramètres → coche « Privé » pour Zanshin.', '1) Celular e PC no mesmo Wi‑Fi — nada de dados móveis, rede de convidados ou VPN.\n2) O endereço no celular precisa ser igual ao de cima — ele muda depois de reiniciar o roteador.\n3) Configurações → Rede e Internet → Wi‑Fi (ou Ethernet) → sua rede → Tipo de perfil de rede: Rede privada.\n4) Segurança do Windows → Firewall e proteção de rede → Permitir um aplicativo pelo firewall → Alterar configurações → marque “Privada” no Zanshin.')
_tr7('hr.trouble_body', '電話側でシーン「Zanshin」とソース「Tep」を確認し、時計が実際に測っているかも見て。別のプログラムがポートを取っているなら、ここと電話の両方で番号を変える。', '检查手机上的场景 “Zanshin” 和来源 “Tep”，并确认手表确实在测量。如果端口被别的程序占用，就在这里和手机上一起改。', 'Проверь на телефоне сцену «Zanshin» и источник «Tep», а также что часы действительно измеряют. Если порт занят другой программой, поменяй его здесь и в телефоне.', 'Comprueba en el móvil la escena «Zanshin» y la fuente «Tep», y que el reloj esté midiendo de verdad. Si otro programa ocupó el puerto, cámbialo aquí y en el móvil.', 'Prüfe am Handy die Szene „Zanshin“ und die Quelle „Tep“ und ob die Uhr wirklich misst. Wenn ein anderes Programm den Port belegt, ändere ihn hier und am Handy.', 'Vérifie sur le téléphone la scène « Zanshin » et la source « Tep », et que la montre mesure vraiment. Si un autre programme a pris le port, change-le ici et sur le téléphone.', 'Verifique no celular a cena “Zanshin” e a fonte “Tep”, e se o relógio está medindo de verdade. Se outro programa ocupou a porta, mude-a aqui e no celular.')
_tr7('hr.qr_show', '電話で読み取る', '用手机扫描', 'Отсканировать телефоном', 'Escanear con el móvil', 'Mit dem Handy scannen', 'Scanner avec le téléphone', 'Ler com o celular')
_tr7('hr.qr_hide', 'コードを隠す', '隐藏二维码', 'Скрыть коды', 'Ocultar los códigos', 'Codes ausblenden', 'Masquer les codes', 'Esconder os códigos')
_tr7('hr.qr_android', 'Android / Wear OS\n「HeartRateOnStream for OBS」（無料）。\nアドレスとポートは「時計のつなぎ方…」にある。', 'Android / Wear OS\n“HeartRateOnStream for OBS”（免费）。\n地址和端口在“如何连接手表…”里。', 'Android / Wear OS\n«HeartRateOnStream for OBS» (бесплатно).\nАдрес и порт — в «Как подключить часы…».', 'Android / Wear OS\n«HeartRateOnStream for OBS» (gratis).\nLa dirección y el puerto están en «Cómo vincular tu reloj…».', 'Android / Wear OS\n„HeartRateOnStream for OBS“ (kostenlos).\nAdresse und Port findest du unter „Uhr verbinden…“.', 'Android / Wear OS\n« HeartRateOnStream for OBS » (gratuit).\nL’adresse et le port sont dans « Comment connecter ta montre… ».', 'Android / Wear OS\n“HeartRateOnStream for OBS” (grátis).\nO endereço e a porta estão em “Como parear o seu relógio…”.')
_tr7('settings.auto_profile_unavailable', 'ゲームによる自動切り替えは今は使えない（psutil ライブラリがない）', '目前无法按游戏自动切换（缺少 psutil 库）', 'Автопереключение по игре сейчас недоступно (нет библиотеки psutil)', 'El cambio automático por juego no está disponible ahora (falta la librería psutil)', 'Automatischer Wechsel nach Spiel ist gerade nicht verfügbar (Bibliothek psutil fehlt)', 'Le changement automatique par jeu n’est pas disponible (bibliothèque psutil manquante)', 'A troca automática por jogo não está disponível agora (falta a biblioteca psutil)')
_tr7('settings.hr_section_title', '時計と心拍', '手表与心率', 'Часы и пульс', 'Reloj y pulso', 'Uhr und Puls', 'Montre et pouls', 'Relógio e pulso')
_tr7('settings.hr_ip_hint', '0.0.0.0 のままに。この番号は電話に入れない — 正しいアドレスは「時計のつなぎ方…」にある。', '保持 0.0.0.0。不要把这个号码填进手机——正确的地址在“如何连接手表…”里。', 'Оставь 0.0.0.0. В телефон это число не вводи — правильный адрес есть в «Как подключить часы…».', 'Deja 0.0.0.0. No escribas este número en el móvil: la dirección correcta está en «Cómo vincular tu reloj…».', 'Lass 0.0.0.0. Diese Zahl nicht ins Handy eintippen — die richtige Adresse steht unter „Uhr verbinden…“.', 'Laisse 0.0.0.0. Ne tape pas ce numéro dans le téléphone — la bonne adresse est dans « Comment connecter ta montre… ».', 'Deixe 0.0.0.0. Não digite este número no celular — o endereço certo está em “Como parear o seu relógio…”.')
_tr7('settings.hr_port_hint', '4455 のままで — 同じ番号を電話のアプリに入力します。', '保留 4455——在手机应用里输入同样的号码。', 'Оставь 4455 — то же число ты введёшь в приложении на телефоне.', 'Deja 4455: el mismo número lo pones en la app del móvil.', 'Lass 4455 stehen — dieselbe Zahl gibst du in der Handy-App ein.', 'Laisse 4455 — tu saisis le même numéro dans l’app du téléphone.', 'Deixe 4455 — o mesmo número você coloca no app do celular.')
_tr7('settings.hr_enable_switch', '電話から心拍を受け取る', '接收手机发来的心率', 'Принимать пульс с телефона', 'Recibir el pulso del móvil', 'Puls vom Handy empfangen', 'Recevoir le pouls du téléphone', 'Receber o pulso do celular')
_tr7('settings.volume', '音量', '音量', 'Громкость', 'Volumen', 'Lautstärke', 'Volume', 'Volume')
_tr7('settings.volume_sub', '合図だけに効く。ゲームの音量は変わらない。', '只影响提示。不会改变游戏音量。', 'Действует только на подсказки. Громкость игры не меняется.', 'Solo afecta a los avisos. No cambia el volumen del juego.', 'Gilt nur für die Hinweise. Die Spiellautstärke ändert sich nicht.', 'Ne concerne que les rappels. Ne change pas le volume du jeu.', 'Só se aplica aos avisos. Não muda o volume do jogo.')
_tr7('settings.balance', '効果音 ↔ 音声のバランス', '音效 ↔ 语音 比例', 'Баланс звук ↔ голос', 'Mezcla sonido ↔ voz', 'Verhältnis Ton ↔ Stimme', 'Équilibre son ↔ voix', 'Mistura som ↔ voz')
_tr7('settings.balance_sub', '音量を効果音と話し声にどう配分するか。左は効果音寄り、右は音声寄り。', '音量在音效和语音之间如何分配。偏左更偏音效，偏右更偏语音。', 'Как громкость делится между звуковым эффектом и голосом. Влево — больше звука, вправо — больше голоса.', 'Cómo se reparte el volumen entre el efecto de sonido y la voz. A la izquierda manda el sonido; a la derecha, la voz.', 'Wie sich die Lautstärke zwischen Soundeffekt und Stimme aufteilt. Links führt der Ton, rechts die Stimme.', 'Comment le volume se répartit entre l’effet sonore et la voix. À gauche le son domine, à droite la voix.', 'Como o volume se divide entre o efeito sonoro e a voz. À esquerda manda o som, à direita a voz.')
_tr7('settings.balance_center', '半々', '各半', 'поровну', 'a partes iguales', 'halb-halb', 'à parts égales', 'meio a meio')
_tr7('settings.balance_sfx', '効果音', '音效', 'звук', 'sonido', 'Ton', 'son', 'som')
_tr7('settings.balance_tts', '音声', '语音', 'голос', 'voz', 'Stimme', 'voix', 'voz')
_tr7('settings.engine', '音声の種類', '语音来源', 'Источник голоса', 'Origen de la voz', 'Stimmquelle', 'Source de la voix', 'Fonte da voz')
_tr7('settings.engine_sub', '自然な音声のほうがきれいですが、合図の文面（心拍は決して送りません）を音声に変換するため Microsoft に送ります — 送るのは見守っていないときだけです。Windows の音声は何も送りません。', '自然语音听起来更好，但它会把提示的文字（绝不包括心率）发送给 Microsoft 转换成语音——只在我没有关注时发送。Windows 语音什么都不发送。', 'Естественный голос звучит лучше, но отправляет текст подсказок (но никогда не пульс) в Microsoft для преобразования в речь — только пока я не наблюдаю. Голос Windows ничего не отправляет.', 'La voz natural suena mejor, pero envía el texto de los avisos (nunca tu pulso) a Microsoft para convertirlo en voz, solo mientras no estoy observando. La voz de Windows no envía nada.', 'Die natürliche Stimme klingt besser, schickt aber den Text der Hinweise (nie deinen Puls) zur Umwandlung in Sprache an Microsoft — nur, solange ich nicht beobachte. Die Windows-Stimme schickt nichts.', 'La voix naturelle sonne mieux, mais elle envoie le texte des rappels (jamais ton pouls) à Microsoft pour le convertir en parole — seulement quand je n’observe pas. La voix Windows n’envoie rien.', 'A voz natural soa melhor, mas envia o texto dos avisos (nunca o seu pulso) à Microsoft para virar fala — só enquanto não estou observando. A voz do Windows não envia nada.')
_tr7('settings.voice', '音声', '语音', 'Голос', 'Voz', 'Stimme', 'Voix', 'Voz')
_tr7('settings.voice_sub', '自分の音声を持たないすべての合図に使います。', '用于所有没有单独设置语音的提示。', 'Для каждой подсказки без собственного голоса.', 'Para cada aviso sin voz propia.', 'Für jeden Hinweis ohne eigene Stimme.', 'Pour chaque rappel sans voix propre.', 'Para cada aviso sem voz própria.')
_tr7('settings.rate', '話す速さ', '语速', 'Скорость речи', 'Velocidad del habla', 'Sprechtempo', 'Vitesse de parole', 'Velocidade da fala')
_tr7('settings.rate_sub', 'マイナスで遅く、プラスで速く。ストレス下ではゆっくりのほうが聞き取りやすい。', '负数变慢，正数变快。压力大时慢一点更容易听懂。', 'Минус замедляет, плюс ускоряет. Под стрессом медленную речь легче воспринимать.', 'El menos la ralentiza y el más la acelera. Bajo estrés se sigue mejor un habla más lenta.', 'Minus verlangsamt, Plus beschleunigt. Unter Stress folgt man langsamerer Sprache leichter.', 'Le moins ralentit, le plus accélère. Sous stress, une parole plus lente est plus facile à suivre.', 'O menos deixa mais lenta, o mais acelera. Sob estresse, uma fala mais lenta é mais fácil de acompanhar.')
_tr7('settings.preview', 'どう聞こえるか', '听起来如何', 'Как это звучит', 'Cómo suena', 'Wie es klingt', 'Comment ça sonne', 'Como soa')
_tr7('settings.preview_sub', '最初の合図を、ゲーム中とまったく同じように鳴らす — この音声、この音量、このバランスで。', '按游戏中的原样播放第一条提示——用当前的语音、音量和比例。', 'Проигрывает первую подсказку ровно так, как она прозвучит в игре — этим голосом, громкостью и балансом.', 'Reproduce el primer aviso exactamente como sonará en el juego, con esta voz, volumen y mezcla.', 'Spielt den ersten Hinweis genau so, wie er im Spiel klingen wird — mit dieser Stimme, Lautstärke und Mischung.', 'Joue le premier rappel exactement comme il sonnera en jeu — avec cette voix, ce volume et cet équilibre.', 'Toca o primeiro aviso exatamente como soará no jogo — com esta voz, volume e mistura.')
_tr7('settings.preview_btn', '試す', '试听', 'Попробовать', 'Probar', 'Ausprobieren', 'Essayer', 'Experimentar')
_tr7('settings.audio_voice_title', '合図の音声', '提示语音', 'Голос подсказок', 'Voz de los avisos', 'Stimme der Hinweise', 'Voix des rappels', 'Voz dos avisos')
_tr7('settings.audio_volume_title', '音の大きさ', '响度', 'Громкость', 'Volumen', 'Lautstärke', 'Volume sonore', 'Volume')
_tr7('settings.speed_slow', 'ゆっくり', '慢', 'медленно', 'lento', 'langsam', 'lent', 'lento')
_tr7('settings.speed_normal', 'ふつう', '正常', 'нормально', 'normal', 'normal', 'normal', 'normal')
_tr7('settings.speed_fast', '速く', '快', 'быстро', 'rápido', 'schnell', 'rapide', 'rápido')
_tr7('settings.audio_reset', '推奨値に戻す', '恢复推荐值', 'Вернуть рекомендуемые', 'Restaurar los recomendados', 'Empfohlene wiederherstellen', 'Rétablir les valeurs recommandées', 'Restaurar os recomendados')
_tr7('settings.audio_reset_btn', '戻す', '恢复', 'Вернуть', 'Restaurar', 'Zurücksetzen', 'Rétablir', 'Restaurar')
_tr7('settings.look_title', '見た目と言語', '外观与语言', 'Вид и язык', 'Aspecto e idioma', 'Aussehen und Sprache', 'Apparence et langue', 'Aparência e idioma')
_tr7('settings.language', '言語', '语言', 'Язык', 'Idioma', 'Sprache', 'Langue', 'Idioma')
_tr7('settings.language_sub', 'すでにある合図の文言は変わりません。', '已有提示的文字不会改变。', 'Уже созданные подсказки сохранят свой текст.', 'Los avisos que ya tienes conservan su texto.', 'Hinweise, die du schon hast, behalten ihren Wortlaut.', 'Les rappels que tu as déjà gardent leur texte.', 'Os avisos que você já tem continuam com o mesmo texto.')
_tr7('settings.guide_title', 'ガイド', '指南', 'Справочник', 'Guía', 'Leitfaden', 'Guide', 'Guia')
_tr7('settings.guide_row', 'なぜ顎、重心、呼吸なのか', '为什么是下巴、重心和呼吸', 'Почему челюсть, центр тяжести и дыхание', 'Por qué mandíbula, centro y respiración', 'Warum Kiefer, Schwerpunkt und Atem', 'Pourquoi mâchoire, ancrage et souffle', 'Por que mandíbula, centro e respiração')
_tr7('settings.tour_row', 'アプリのツアー', '应用导览', 'Экскурсия по приложению', 'Recorrido por la app', 'App-Tour', 'Visite de l’app', 'Visita ao app')
_tr7('settings.tour_row_at', 'アプリのツアー — ステップ {n} / {total}', '应用导览——第 {n} 步，共 {total} 步', 'Экскурсия по приложению — шаг {n} из {total}', 'Recorrido por la app: paso {n} de {total}', 'App-Tour — Schritt {n} von {total}', 'Visite de l’app — étape {n} sur {total}', 'Visita ao app — passo {n} de {total}')
_tr7('settings.tour_sub', 'どこに何があるかの短い案内。', '简短介绍东西都在哪儿。', 'Короткая экскурсия по тому, где что находится.', 'Un recorrido breve por dónde está cada cosa.', 'Eine kurze Tour, wo was ist.', 'Une brève visite de l’endroit où se trouve quoi.', 'Uma visita curta a onde está o quê.')
_tr7('settings.tour_btn', 'ツアーを始める', '开始导览', 'Начать экскурсию', 'Empezar el recorrido', 'Tour starten', 'Démarrer la visite', 'Iniciar a visita')
_tr7('settings.tour_resume', '続ける', '继续', 'Продолжить', 'Continuar', 'Fortsetzen', 'Continuer', 'Continuar')
_tr7('settings.speed_normal', 'ふつう', '正常', 'нормально', 'normal', 'normal', 'normal', 'normal')
_tr7('history.title', 'セッション履歴', '记录历史', 'История сессий', 'Historial de sesiones', 'Sitzungsverlauf', 'Historique des séances', 'Histórico de sessões')
_tr7('history.subtitle', '心拍が1分以上あるセッションがここに保存されます（直近 400 件）。', '这里保存至少有一分钟心率的记录（最近 400 次）。', 'Здесь сохраняются сессии, где пульс шёл хотя бы минуту (последние 400).', 'Aquí se guardan las sesiones con al menos un minuto de pulso (las últimas 400).', 'Hier landen Sitzungen mit mindestens einer Minute Puls (die letzten 400).', 'Les séances avec au moins une minute de pouls sont enregistrées ici (les 400 dernières).', 'Aqui ficam as sessões com pelo menos um minuto de pulso (as últimas 400).')
_tr7('history.insights_title', '私が気づいたこと', '我注意到的事', 'Что я заметила', 'Lo que he notado', 'Was mir aufgefallen ist', 'Ce que j’ai remarqué', 'O que eu notei')
_tr7('history.analysis_running', '履歴を分析中…', '正在分析历史…', 'Анализирую историю…', 'Analizando el historial…', 'Verlauf wird analysiert…', 'Analyse de l’historique…', 'Analisando o histórico…')
_tr7('history.analysis_stamp', '{when} の分析', '{when} 的分析', 'Анализ от {when}', 'Análisis de {when}', 'Analyse vom {when}', 'Analyse du {when}', 'Análise de {when}')
_tr7('history.recompute', '再計算', '重新计算', 'Пересчитать', 'Recalcular', 'Neu berechnen', 'Recalculer', 'Recalcular')
_tr7('history.trend_title', 'セッションをまたいだ推移', '跨记录的趋势', 'Динамика по сессиям', 'Evolución entre sesiones', 'Verlauf über die Sitzungen', 'Évolution entre séances', 'Evolução entre sessões')
_tr7('history.trend_delta', '{first} → {last} BPM、推移 {slope} BPM/週', '{first} → {last} BPM，趋势 {slope} BPM/周', '{first} → {last} уд/мин, тренд {slope} уд/мин в неделю', '{first} → {last} ppm, tendencia {slope} ppm/semana', '{first} → {last} S/min, Trend {slope} S/min pro Woche', '{first} → {last} bpm, tendance {slope} bpm/semaine', '{first} → {last} bpm, tendência {slope} bpm/semana')
_tr7('history.trend_need_more', 'セッションがまだ近すぎて推移が出せない — 数日たってからまた見て。', '记录之间还太密集，看不出趋势——过几天再来看。', 'Сессии пока слишком близко друг к другу для тренда — загляни через несколько дней.', 'Las sesiones están aún demasiado juntas para una tendencia: vuelve dentro de unos días.', 'Die Sitzungen liegen für einen Trend noch zu dicht beieinander — schau in ein paar Tagen wieder rein.', 'Les séances sont encore trop rapprochées pour une tendance — reviens dans quelques jours.', 'As sessões ainda estão muito próximas para uma tendência — volte daqui a alguns dias.')
_tr7('history.empty_period', 'この期間にはまだ何もない。', '这个时间段还没有内容。', 'В этом периоде пока ничего.', 'Todavía no hay nada en este periodo.', 'In diesem Zeitraum noch nichts.', 'Rien dans cette période pour l’instant.', 'Ainda nada neste período.')
_tr7('history.period.day', '日', '天', 'День', 'Día', 'Tag', 'Jour', 'Dia')
_tr7('history.period.week', '週', '周', 'Неделя', 'Semana', 'Woche', 'Semaine', 'Semana')
_tr7('history.period.month', '月', '月', 'Месяц', 'Mes', 'Monat', 'Mois', 'Mês')
_tr7('history.period.year', '年', '年', 'Год', 'Año', 'Jahr', 'Année', 'Ano')
_tr7('history.pick_metric', '指標', '指标', 'Метрика', 'Métrica', 'Kennzahl', 'Mesure', 'Métrica')
_tr7('history.pick_period', '期間', '时间段', 'Период', 'Periodo', 'Zeitraum', 'Période', 'Período')
_tr7('history.band_label', 'あなたのふつうの幅', '你的常见范围', 'твой обычный диапазон', 'tu rango habitual', 'dein üblicher Bereich', 'ta plage habituelle', 'a sua faixa habitual')
_tr7('history.unit.hrr', '1分あたりの BPM', '每分钟 BPM', 'BPM за минуту', 'BPM por minuto', 'BPM pro Minute', 'BPM par minute', 'BPM por minuto')
_tr7('history.unit.over', '分', '分钟', 'минуты', 'minutos', 'Minuten', 'minutes', 'minutos')
_tr7('history.unit.peak', '0〜100 のうち', '满分 100', 'из 0–100', 'de 0–100', 'von 0–100', 'sur 0–100', 'de 0–100')
_tr7('history.sessions_title', 'セッション', '记录', 'Сессии', 'Sesiones', 'Sitzungen', 'Séances', 'Sessões')
_tr7('history.sessions_count', '{n} セッション', '{n} 次记录', 'Сессий: {n}', '{n} sesiones', '{n} Sitzungen', '{n} séances', '{n} sessões')
_tr7('history.col_date', '日付', '日期', 'Дата', 'Fecha', 'Datum', 'Date', 'Data')
_tr7('history.col_duration', '長さ', '时长', 'Длина', 'Duración', 'Länge', 'Durée', 'Duração')
_tr7('history.col_avg', '平均', '平均', 'Среднее', 'Media', 'Schnitt', 'Moyenne', 'Média')
_tr7('history.col_over', '上限超え', '超上限', 'Выше границы', 'Sobre el límite', 'Über Grenze', 'Au-delà limite', 'Acima do limite')
_tr7('history.col_peak', '負荷のピーク', '负荷峰值', 'Пик нагрузки', 'Pico de carga', 'Last-Spitze', 'Pic de charge', 'Pico de carga')
_tr7('history.info_more', 'ⓘ どういう意味', 'ⓘ 这是什么意思', 'ⓘ что это значит', 'ⓘ qué significa', 'ⓘ was das bedeutet', 'ⓘ ce que ça veut dire', 'ⓘ o que significa')
_tr7('history.info_less', 'ⓘ 隠す', 'ⓘ 隐藏', 'ⓘ скрыть', 'ⓘ ocultar', 'ⓘ ausblenden', 'ⓘ masquer', 'ⓘ esconder')
_tr7('history.export_extra', 'あわせて保存されました：\n{files}', '同时还保存了：\n{files}', 'Вместе с этим сохранено:\n{files}', 'También se guardó lo siguiente:\n{files}', 'Zusätzlich gespeichert:\n{files}', 'Enregistré également :\n{files}', 'Junto com ele, também foram salvos:\n{files}')
_tr7('history.export_col.longest_above_s', 'しきい値超えの最長 (秒)', '超过阈值最长 (秒)', 'самый долгий отрезок выше порога (с)', 'tramo más largo sobre el umbral (s)', 'längste Zeit über der Schwelle (s)', 'plus longue durée au-dessus du seuil (s)', 'trecho mais longo acima do limiar (s)')
_tr7('history.export_col.above_runs', 'しきい値超えの回数', '超阈值次数', 'участки выше порога', 'tramos sobre el umbral', 'Abschnitte über der Schwelle', 'segments au-dessus du seuil', 'trechos acima do limiar')
_tr7('history.export_col.cancelled_dip', '低下で中断', '因回落中断', 'отменено спадом', 'cancelado por caída', 'durch Abfall abgebrochen', 'annulé par une baisse', 'cancelado por queda')
_tr7('history.export_col.cancelled_gap', '欠測で中断', '因断连中断', 'отменено пропаданием', 'cancelado por corte', 'durch Ausfall abgebrochen', 'annulé par une coupure', 'cancelado por falha')
_tr7('history.export_col.hold_s', '必要な継続 (秒)', '所需持续 (秒)', 'нужное удержание (с)', 'permanencia necesaria (s)', 'nötige Haltedauer (s)', 'maintien requis (s)', 'permanência necessária (s)')
_tr7('history.export_col.context', '文脈', '情境', 'контекст', 'contexto', 'Kontext', 'contexte', 'contexto')
_tr7('history.effect_few', '今は {n} 件 — 判断には足りません', '目前 {n} 次——还不足以下结论', 'пока {n} — мало для выводов', 'por ahora {n}: pocos para afirmar nada', 'bisher {n} — zu wenig für eine Aussage', 'pour l’instant {n} — trop peu pour conclure', 'por agora {n} — poucos para afirmar')
_tr7('history.effect_empty', '測定できる合図がまだ一度も鳴っていません。', '还没有任何可供测量的提示响起。', 'Пока не прозвучала ни одна подсказка, которую можно измерить.', 'Todavía no ha sonado ningún aviso que se pueda medir.', 'Es ist noch kein Hinweis erklungen, den man messen könnte.', 'Aucun rappel mesurable n’a encore retenti.', 'Ainda não soou nenhum aviso que se possa medir.')
_tr7('cue.category.grounding', '重心', '重心', 'опора', 'centro', 'Schwerpunkt', 'ancrage', 'centro')
_tr7('cue.category.jaw', '顎', '下颌', 'челюсть', 'mandíbula', 'Kiefer', 'mâchoire', 'mandíbula')
_tr7('cue.category.release', '手と視線', '手与视线', 'рука и взгляд', 'mano y mirada', 'Hand und Blick', 'main et regard', 'mão e olhar')
_tr7('cue.category.breath', '呼吸', '呼吸', 'дыхание', 'respiración', 'Atem', 'souffle', 'respiração')
_tr7('history.rhythm_title', '続けぐあい', '规律性', 'Регулярность', 'Constancia', 'Regelmäßigkeit', 'Régularité', 'Regularidade')
_tr7('history.days_played', 'セッションのあった日 · {weeks}週', '有记录的天数 · {weeks}周', 'Дней с сессией · {weeks} нед.', 'Días con sesión · {weeks} sem.', 'Tage mit Sitzung · {weeks} Wo.', 'Jours avec séance · {weeks} sem.', 'Dias com sessão · {weeks} sem.')
_tr7('history.grid_less', '少ない', '较少', 'меньше', 'menos', 'weniger', 'moins', 'menos')
_tr7('history.grid_more', '多い', '较多', 'больше', 'más', 'mehr', 'plus', 'mais')
_tr7('history.detail_title', 'セッションを間近で', '近看一次记录', 'Одна сессия вблизи', 'Una sesión de cerca', 'Eine Sitzung aus der Nähe', 'Une séance de près', 'Uma sessão de perto')
_tr7('history.detail_peak', '最高心拍', '最高心率', 'Самый высокий пульс', 'Pulso más alto', 'Höchster Puls', 'Pouls le plus haut', 'Pulso mais alto')
_tr7('history.detail_hrr', '回復', '恢复', 'Восстановление', 'Recuperación', 'Erholung', 'Récupération', 'Recuperação')
_tr7('history.detail_hint', '表の行をクリックすると、別のセッションを見られる。', '点击表格中的某一行即可查看另一次记录。', 'Нажми на строку в таблице, чтобы посмотреть другую сессию.', 'Haz clic en una fila de la tabla para ver otra sesión.', 'Klick auf eine Zeile in der Tabelle, um eine andere Sitzung anzusehen.', 'Clique sur une ligne du tableau pour voir une autre séance.', 'Clique numa linha da tabela para ver outra sessão.')
_tr7('history.detail_empty', 'まだセッションがない — ここにその曲線が出る。', '还没有记录——它的曲线会显示在这里。', 'Сессий пока нет — здесь появится её кривая.', 'Aún no hay sesiones: aquí aparecerá su curva.', 'Noch keine Sitzung — hier erscheint ihre Kurve.', 'Pas encore de séance — sa courbe apparaîtra ici.', 'Ainda não há sessão — a sua curva aparece aqui.')
_tr7('history.detail_no_curve', 'このセッションは古いバージョンのもので、曲線はもう復元できない。新しいセッションは保存している。', '这次记录来自旧版本，曲线已无法还原。新的记录会保存曲线。', 'Эта сессия из более старой версии, её кривую уже не восстановить. Новые сессии её сохраняют.', 'Esta sesión viene de una versión anterior, así que su curva ya no se puede reconstruir. Las nuevas sí la guardan.', 'Diese Sitzung stammt aus einer älteren Version, ihre Kurve lässt sich nicht mehr rekonstruieren. Neue Sitzungen speichern sie.', 'Cette séance vient d’une version plus ancienne, sa courbe ne peut plus être reconstituée. Les nouvelles la conservent.', 'Esta sessão vem de uma versão mais antiga, por isso a curva já não pode ser reconstruída. As novas a salvam.')
_tr7('history.export_btn', '表にエクスポート', '导出为表格', 'Экспорт в таблицу', 'Exportar a una hoja de cálculo', 'In eine Tabelle exportieren', 'Exporter vers un tableur', 'Exportar para uma planilha')
_tr7('history.export_filetype', 'Excel 用の表（CSV）', 'Excel 表格（CSV）', 'Таблица для Excel (CSV)', 'Hoja de cálculo de Excel (CSV)', 'Excel-Tabelle (CSV)', 'Tableur Excel (CSV)', 'Planilha do Excel (CSV)')
_tr7('history.export_empty', 'エクスポートするものがまだない — まず心拍センサーつきでセッションをこなして。', '还没有可导出的内容——先带着心率传感器玩一次。', 'Пока нечего экспортировать — сначала проведи сессию с датчиком пульса.', 'Todavía no hay nada que exportar: juega antes una sesión con el sensor de pulso.', 'Noch nichts zum Exportieren — spiel zuerst eine Sitzung mit dem Pulssensor.', 'Rien à exporter pour l’instant — joue d’abord une séance avec le capteur de pouls.', 'Ainda não há nada para exportar — jogue primeiro uma sessão com o sensor de pulso.')
_tr7('history.export_done', '{n} セッションを {path} に保存した。', '已把 {n} 次记录保存到 {path}。', 'Сохранено сессий: {n} — в {path}.', 'Se guardaron {n} sesiones en {path}.', '{n} Sitzungen in {path} gespeichert.', '{n} séances enregistrées dans {path}.', 'Foram salvas {n} sessões em {path}.')
_tr7('history.export_failed', 'エクスポートに失敗した：{err}', '导出失败：{err}', 'Экспорт не удался: {err}', 'La exportación falló: {err}', 'Export fehlgeschlagen: {err}', 'L’export a échoué : {err}', 'A exportação falhou: {err}')
_tr7('history.export_col.date', '日付', '日期', 'Дата', 'Fecha', 'Datum', 'Date', 'Data')
_tr7('history.export_col.start', '開始', '开始', 'Начало', 'Inicio', 'Beginn', 'Début', 'Início')
_tr7('history.export_col.duration_min', '長さ（分）', '时长（分钟）', 'Длительность (мин)', 'Duración (min)', 'Länge (Min)', 'Durée (min)', 'Duração (min)')
_tr7('history.export_col.avg_bpm', '平均 BPM', '平均 BPM', 'Средний BPM', 'BPM medio', 'Durchschnitts-BPM', 'BPM moyen', 'BPM médio')
_tr7('history.export_col.min_bpm', '最低 BPM', '最低 BPM', 'Минимальный BPM', 'BPM mínimo', 'Niedrigster BPM', 'BPM le plus bas', 'BPM mais baixo')
_tr7('history.export_col.max_bpm', '最高 BPM', '最高 BPM', 'Максимальный BPM', 'BPM máximo', 'Höchster BPM', 'BPM le plus haut', 'BPM mais alto')
_tr7('history.export_col.baseline_bpm', '安静時ベースライン', '静息基线', 'Базовая линия покоя', 'Línea base en reposo', 'Ruhebasislinie', 'Ligne de base au repos', 'Linha de base em repouso')
_tr7('history.export_col.over_min', '上限超え（分）', '超上限（分钟）', 'Выше границы (мин)', 'Sobre el límite (min)', 'Über der Grenze (Min)', 'Au-dessus de la limite (min)', 'Acima do limite (min)')
_tr7('history.export_col.peak_stress', '負荷のピーク', '负荷峰值', 'Пик нагрузки', 'Pico de carga', 'Last-Spitze', 'Pic de charge', 'Pico de carga')
_tr7('history.export_col.hrr_bpm', '回復（HRR）', '恢复（HRR）', 'Восстановление (HRR)', 'Recuperación (HRR)', 'Erholung (HRR)', 'Récupération (HRR)', 'Recuperação (HRR)')
_tr7('history.export_col.calm_min', '平静（分）', '平静（分钟）', 'Покой (мин)', 'Calma (min)', 'Ruhig (Min)', 'Calme (min)', 'Calmo (min)')
_tr7('history.export_col.raised_min', 'やや上昇（分）', '略高（分钟）', 'Повышенная (мин)', 'Elevada (min)', 'Erhöht (Min)', 'Élevée (min)', 'Elevada (min)')
_tr7('history.export_col.high_min', '高い（分）', '偏高（分钟）', 'Высокая (мин)', 'Alta (min)', 'Hoch (Min)', 'Haute (min)', 'Alta (min)')
_tr7('history.export_col.critical_min', 'ピーク（分）', '高峰（分钟）', 'Пик (мин)', 'Pico (min)', 'Spitze (Min)', 'Pic (min)', 'Pico (min)')

# --- language of what the app draws INTO THE GAME ----------------------
# Separate from the window language: the HUD bottom left and the labels
# under the visuals end up on a stream and on store screenshots, where
# people who do not know the interface language read them too.
STRINGS.update({
    'settings.game_lang': _sk_en('Jazyk v hre', 'In-game language'),
    'settings.game_lang_same': _sk_en('Rovnaký ako appka', 'Same as the app'),
    'settings.game_lang_sub': _sk_en(
        'Jazyk textu, ktorý kreslím do hry — panel s tepom aj popisky pod obrázkami. Toto vidia aj diváci na streame, preto je predvolená angličtina, aj keď appka beží po slovensky.',
        'The language of the text I draw into the game — the heart-rate panel and the captions under the pictures. Your stream viewers see this too, so English is the default even when the app itself is not.'),
    'log.game_lang': _sk_en('Jazyk v hre: {lang}', 'In-game language: {lang}'),
})
_tr7('settings.game_lang', 'ゲーム中の言語', '游戏中的语言', 'Язык в игре', 'Idioma en el juego', 'Sprache im Spiel', 'Langue en jeu', 'Idioma no jogo')
_tr7('settings.game_lang_same', 'アプリと同じ', '与应用相同', 'Как в приложении', 'El mismo que la app', 'Wie die App', 'Comme l’app', 'O mesmo do app')
_tr7('settings.game_lang_sub', '私がゲーム中に描く文字の言語 — 心拍パネルと画像の下の説明。これはストリームの視聴者にも見えるので、アプリ自体が別の言語でも既定は英語。', '我绘制到游戏里的文字语言——心率面板和图片下方的说明。直播观众也会看到，所以即使应用本身不是英文，默认也用英文。', 'Язык текста, который я рисую в игре, — панель пульса и подписи под картинками. Это видят и зрители на стриме, поэтому по умолчанию английский, даже если само приложение на другом языке.', 'El idioma del texto que dibujo dentro del juego: el panel de pulso y los rótulos bajo las imágenes. Tus espectadores también lo ven, por eso el inglés es el valor por defecto aunque la app no lo esté.', 'Die Sprache des Textes, den ich ins Spiel zeichne — das Puls-Panel und die Beschriftungen unter den Bildern. Das sehen auch deine Stream-Zuschauer, deshalb ist Englisch die Vorgabe, selbst wenn die App es nicht ist.', 'La langue du texte que je dessine dans le jeu — le panneau de pouls et les légendes sous les images. Tes spectateurs le voient aussi, c’est pourquoi l’anglais est la valeur par défaut même si l’app ne l’est pas.', 'O idioma do texto que eu desenho dentro do jogo — o painel de pulso e as legendas embaixo das imagens. Os seus espectadores também o veem, por isso o inglês é o padrão mesmo quando o app em si não está em inglês.')

# --- effectiveness measurement --------------------------------------------
# NOTE: 'efficacy.empty' was here - the empty state of the Effectiveness
# page, a new screen from phase 5 that does not exist yet. Nothing called
# it, so the key was deleted with the other unused ones. The decided
# wording, for when the page is built: "Zatiaľ nič. Nazbiera sa to hraním,
# nie čakaním." (Nothing yet. This builds up by playing, not by waiting.) -
# sessions already exist, there are just not enough of them yet for a
# comparison, so it points to no button; the only answer is to keep playing.
# Its other nine languages are in git history (commit 3414450, i18n.py and
# i18n_cs_bg.py).
STRINGS.update({
    # Log line after a delivered cue. The SAME in both arms - in the voice
    # arm and in the silent one. The player hears anyway whether something
    # sounded, so it cannot be blinded anyway, but the log should not be yet
    # another place where the arms differ. That is why there is not a word
    # here about whether anything was spoken.
    'log.cue_delivered': _sk_en(
        'Ozvala som sa: {label}',
        'I spoke up: {label}'),
    'log.cue_visual_failed': _sk_en(
        'Obrázok v hre sa nevykreslil — táto pripomienka sa do merania nezaráta.',
        'The in-game picture didn’t draw — this cue won’t count in the measurement.'),
})

# --- heart rate dropout: quiet and truthful --------------------------------
# Heart rate the app was hearing stopped coming (after 12 s of silence or
# when the watch drops the connection). This is not "nothing has arrived
# yet" - hence its own sentence under the heading "Waiting for heart rate"
# and its own label on Today. No sound, window or new text in the game:
# the HUD shows "--" as before.
# The chain heart rate travels is watch → phone (Bluetooth) → Wi‑Fi →
# computer; the advice on a dropout (`insight.cue_dropouts`,
# `session.end.none_dropouts`) describes the same chain.
STRINGS.update({
    'dnes.hr_lost': _sk_en('tep vypadol', 'heart rate lost'),
    # 0.3: instead of "waiting for the watch" where the watch cannot come
    # (`app_today._text_bez_tepu`).
    'dnes.hr_off': _sk_en('príjem tepu vypnutý', 'heart-rate receiving off'),
    'dnes.hr_busy': _sk_en('port je obsadený', 'port is busy'),
    'dnes.hr_no_client': _sk_en('telefón sa nepripojil', 'phone didn’t connect'),
    'kamae.lost_sub': _sk_en(
        'Tep prestal chodiť (hodinky, telefón alebo Wi‑Fi). Kým sa nevráti, nič nemeriam a sama sa neozvem.',
        'Your heart rate stopped coming in (watch, phone or Wi‑Fi). Until it is back, I measure nothing and will not speak up on my own.'),
    'log.hr_back': _sk_en('Tep je späť po {s} s bez signálu.',
                          'Heart rate is back after {s} s without signal.'),
})

# --- end of session: context, not a rating -------------------------------
# It does not ask how the player felt. It asks WHAT WAS GOING ON - so
# that evenings when they talked for two hours can be filtered out.
# Talking is the worst confounder in this measurement: breathing changes
# and heart rate goes up, so a cue looks ineffective, although it has
# nothing to do with it.
#
# "Skip" must be a button as big as "Save". If it were smaller, at some
# point it gets clicked away blindly - and that is worse data than if
# the person filled in nothing.
STRINGS.update({
    'session.end.title': _sk_en(
        'Za tebou je {time} hrania.',
        'You played for {time}.'),
    'session.end.cues': _sk_en(
        'Ozvala som sa {n}×.',
        'I spoke up {n}×.'),
    # Why it did not speak up. Without this, 'neozvala som sa' (I did not
    # speak up) is a statement from which the player cannot tell whether the
    # app is broken, whether they were calm, or whether their watch kept
    # dropping out. Three very different things with very different fixes.
    # Only a fact about the limit, not a verdict about the body: load below
    # the limit does not mean the body was "fine" - the app does not know
    # that and must not claim it.
    'session.end.none_never': _sk_en(
        'Záťaž sa ani raz nedostala nad prah — nemala som prečo sa ozvať.',
        'Your load never crossed the threshold — I had no reason to speak up.'),
    'session.end.none_short': _sk_en(
        'Záťaž hore bola, ale najdlhšie {najdlhsie} s v kuse — potrebujem {treba} s.',
        'Your load did rise, but the longest stretch was {najdlhsie} s — I need {treba} s.'),
    # {n} = how many times a heart rate dropout interrupted counting that
    # had got going (not the number of all dropouts). The advice is the same
    # as in `insight.cue_dropouts`: heart rate goes from the watch via the
    # phone, not from the watch straight to the computer.
    'session.end.none_dropouts': _sk_en(
        'Tep {n}× vypadol práve počas počítania a počítanie sa zakaždým začalo odznova. Tep ide z hodiniek do telefónu cez Bluetooth a z telefónu cez Wi‑Fi do počítača — maj hodinky pri telefóne a telefón blízko Wi‑Fi routra.',
        'Your heart rate dropped out {n}× while I was counting, and each time the count started over. It goes from the watch to the phone over Bluetooth, and from the phone to the PC over Wi‑Fi — keep the watch near the phone and the phone near the Wi‑Fi router.'),
    # CUE GATE (0.2). Not a single pause in input for the session (at least
    # 5 min): the cue had no moment to come (the sentence does not say
    # "voice" - at work it goes without it). Exactly this showed up on a
    # real controller with the gyro on - it is not the player's fault and
    # the sentence does not blame them for anything.
    'session.end.none_nopause': _sk_en(
        'Celý čas som nezachytila ani jednu pauzu vo vstupe — ani pár sekúnd bez klávesnice, myši či ovládača. A práve na ňu čakám, než sa ozvem. Niečo možno hlási vstup bez prestávky, napríklad pohybový senzor ovládača (gyro) alebo páčka bez mŕtvej zóny. Ak hráš s ovládačom, skús v ňom vypnúť gyro.',
        "The whole time I did not catch a single pause in your input — not even a few seconds without keyboard, mouse or controller. And that is exactly what I wait for before I speak up. Something may be reporting input nonstop, such as a controller's motion sensor (gyro) or a stick without a deadzone. If you play with a controller, try turning its gyro off."),
    # The app armed itself, but the gate did not let it through (load was
    # still rising or heart rate was in the critical zone). It decided, not
    # the player.
    'session.end.none_withheld': _sk_en(
        'Záťaž bola hore dosť dlho, ale vhodná chvíľa neprišla — buď ešte stúpala, alebo bol tep v pásme Špička. Radšej som mlčala.',
        'Your load was up long enough, but the right moment never came — it was still climbing, or your pulse was in the peak zone. I chose to stay quiet.'),
    # The gate let a cue through, but the app could not show it
    # (`trigger.A_NEDALO_SA`, `_cue_can_fire` False): the ring at high heart
    # rate was breathing on screen at every such cancellation
    # (`cues_withheld_ring`) - it holds every cue back while it breathes ...
    'session.end.none_ring': _sk_en(
        'Pripomienka bola pripravená, ale na obrazovke práve dýchal dychový kruh pri vysokom tepe, tak som ju podržala.',
        'A cue was ready, but the breath ring for high heart rate was breathing on screen, so I held it back.'),
    # ... or otherwise (no ring, or not at every cancellation): what really
    # stops `_cue_can_fire` in a session - a picture already on screen (the
    # ring included), steps from the watch, all pictures switched off. Not
    # the load, not "not now".
    'session.end.none_blocked': _sk_en(
        'Pripomienka bola pripravená, ale v tej chvíli nemohla prísť — na obrazovke už bol obrázok, hodinky hlásili kroky alebo boli všetky obrázky vypnuté.',
        'A cue was ready, but it could not come at that moment — a picture was already on screen, your watch was reporting steps, or all pictures were off.'),
    'session.end.cues_none': _sk_en('Dnes som sa neozvala ani raz.',
                                    'I did not speak at all today.'),
    # What the player had in their body - the biggest explainable source of
    # variance in the measurement.
    'session.context.body_question': _sk_en('Bolo v tvojom tele niečo z tohto?',
                                            'Did you have any of these in you?'),
    'session.context.save_failed': _sk_en(
        'Kontext sa k tejto relácii nepodarilo uložiť — tvoja odpoveď sa neuchovala.',
        'Could not save the context for this session — your answer was not stored.'),
    'session.context.caffeine': _sk_en('kofeín / energeťák', 'caffeine / energy drink'),
    'session.context.alcohol': _sk_en('alkohol', 'alcohol'),
    'session.context.nicotine': _sk_en('nikotín', 'nicotine'),
    'session.context.question': _sk_en('Dialo sa niečo z tohto?',
                                       'Did any of this happen?'),
    'session.context.why': _sk_en(
        'Keď rozprávaš, mení sa ti dych a tep ide hore. Bez tohto by taký večer vyzeral, že pripomienky nefungujú — hoci s tým nemajú nič spoločné.',
        'When you talk, your breathing changes and your heart rate goes up. Without this, such an evening would look like the cues do nothing — when they have nothing to do with it.'),
    'session.context.call': _sk_en(
        'hovor s niekým',
        'I was on a call'),
    'session.context.laugh': _sk_en(
        'smiech',
        'I was laughing'),
    'session.context.grind': _sk_en('grind', 'grinding'),
    'session.context.competitive': _sk_en('súťažné', 'competitive'),
    'session.context.chill': _sk_en('chill', 'chill'),
    'session.end.skip': _sk_en('Preskočiť', 'Skip'),

    # --- data: deletion, export, import --------------------------------
    'data.title': _sk_en('Tvoje dáta', 'Your data'),
    'data.hint': _sk_en(
        'Tvoj tep, relácie a postrehy ostávajú na tomto počítači. Nastavenia tiež, okrem textu pripomienok: keď hovoria prirodzeným hlasom (Edge, predvolený), pošlem ich text službe Microsoft na prevod do reči. Hlas z Windows nepošle nič.',
        'Your heart rate, sessions and insights stay on this computer. So do your settings, except the wording of your cues: when they speak in the natural voice (Edge, the default), I send their text to Microsoft to turn it into speech. The Windows voice sends nothing.'),
    'data.delete.btn': _sk_en('Zmazať históriu', 'Delete history'),
    'data.delete.title': _sk_en('Zmazať históriu?', 'Delete history?'),
    'data.delete.intro': _sk_en('Zmaže sa toto a späť sa to vrátiť nedá:',
                                'This will be deleted and cannot be undone:'),
    'data.delete.sessions': _sk_en('história relácií', 'session history'),
    'data.delete.events': _sk_en(
        'záznamy pripomienok',
        'cue records'),
    'data.delete.windows': _sk_en('meracie okná', 'measurement windows'),
    'data.delete.insights': _sk_en('postrehy z analýzy', 'computed insights'),
    'data.delete.tts': _sk_en(
        'vyslovené pripomienky (cache)',
        'spoken cues (cache)'),
    'data.delete.backup': _sk_en('záloha', 'backup'),
    # 0.3: checkpoint of the open session (hr_session_open.json).
    'data.delete.open_session': _sk_en('rozpracovaná relácia', 'session in progress'),
    'data.delete.logs': _sk_en('logy', 'logs'),
    'data.delete.empty': _sk_en('(prázdne)', '(empty)'),
    # Copies of the history in old folders after migration
    # (paths.legacy_data_dirs) - one row per folder, only the folder name
    # (the path carries the account name).
    'data.delete.legacy': _sk_en('kópie zo staršej verzie appky (priečinok „{folder}“)',
                                 'copies left by an older version of the app (folder “{folder}”)'),
    'data.delete.done': _sk_en('Zmazané ({n} položiek).', 'Deleted ({n} items).'),
    # 0.2: the bundle carries sessions, measurement windows and insights -
    # not settings, profiles, recordings or cue records. "Everything"
    # promised a move to another PC in which the rest would be lost.
    'data.export.btn': _sk_en('Exportovať históriu (JSON)', 'Export history (JSON)'),
    'data.export.done': _sk_en('Uložené: {path}', 'Saved: {path}'),
    'data.import.btn': _sk_en('Importovať zo súboru', 'Import from a file'),
    'data.import.title': _sk_en('Importovať dáta', 'Import data'),
    'data.import.found': _sk_en('V súbore je {sessions} relácií a {windows} meracích okien.',
                                'The file has {sessions} sessions and {windows} measurement windows.'),
    'data.import.dropped': _sk_en('{n} záznamov sa nedalo prečítať a preskočili sa.',
                                  '{n} records could not be read and were skipped.'),
    # Exactly per the code: `imported` is skipped by hr_stats.ciste_relacie
    # (baseline, high heart rate limit, threshold), the ladder, hr_insights,
    # measure (the effect chart) and hr_stats.posledna_relacia (the last
    # session card).
    'data.import.flagged': _sk_en(
        'Importované záznamy sa označia ako cudzie. V Histórii ich uvidíš, ale neučím sa z nich: nevstúpia do tvojej pokojovej základne, hranice vysokého tepu ani prahu, od ktorého sa ozývam, do postrehov, grafu o pripomienkach, karty poslednej relácie, ani do toho, či sa ozývam hlasom, obrázkom, alebo si dám pauzu. Platí to aj pre tvoj vlastný export z iného počítača.',
        'Imported records are marked as not yours. You will see them in History, but I do not learn from them: they stay out of your resting baseline, your high heart-rate limit and the threshold I speak up at, the insights, the cue chart, the last-session card, and whether I speak up with voice, a picture or take a pause. That goes for your own export from another computer too.'),
    'data.import.question': _sk_en('Zlúčiť ich s tvojimi, alebo nimi tvoje nahradiť?',
                                   'Merge them with yours, or replace yours with them?'),
    'data.import.merge': _sk_en('Zlúčiť s mojimi', 'Merge with mine'),
    'data.import.replace': _sk_en('Nahradiť moje', 'Replace mine'),
    # REPLACE is irreversible against the current files - only on a second
    # click and with a backup (data_io.zaloha_pred_importom).
    'data.import.replace_confirm': _sk_en(
        'Nahradiť prepíše tvoju históriu relácií a meracie okná obsahom '
        'súboru. Predtým ich odložím ako zálohu vedľa pôvodných súborov (s '
        '„pred-importom“ v názve). Naozaj nahradiť?',
        'Replace overwrites your session history and measurement windows with '
        'the contents of the file. Before that I set them aside as a backup '
        'next to the original files (with “pred-importom” in the name). '
        'Replace them?'),
    'data.import.replace_yes': _sk_en('Áno, nahradiť', 'Yes, replace'),
    'data.import.back': _sk_en('Späť', 'Back'),
    'data.import.backup': _sk_en('Pôvodné súbory som odložila ako zálohu: {files}',
                                 'I set the originals aside as a backup: {files}'),
    'data.import.done': _sk_en('Importované: {sessions} relácií, {windows} okien.',
                               'Imported: {sessions} sessions, {windows} windows.'),
    'data.import.not_json': _sk_en('Toto nie je platný JSON súbor.',
                                   'This is not a valid JSON file.'),
    'data.import.unreadable': _sk_en('Súbor sa nedá prečítať.', 'The file cannot be read.'),
    'data.import.foreign': _sk_en('Tento súbor nie je export zo Zanshinu.',
                                  'This file is not a Zanshin export.'),
    'data.import.newer': _sk_en('Súbor je z novšej verzie appky. Aktualizuj appku.',
                                'The file comes from a newer version of the app. Update the app.'),
    'data.import.empty': _sk_en('V súbore nie sú žiadne použiteľné záznamy.',
                                'The file contains no usable records.'),

    # --- developer overlay (§3.2) --------------------------------------
    # The numbers from spec §2 are estimates from the literature, not from
    # this player's body. Without being able to adjust them at runtime it
    # would have to be rebuilt every evening.
    'dev.title': _sk_en('Ladenie', 'Tuning'),
    'dev.hint': _sk_en(
        'Čísla z literatúry, nie z tvojho tela. Menia sa len medzi reláciami — uprostred by sa meral pohyblivý cieľ. Každé meracie okno si pamätá, s akými hodnotami vzniklo.',
        'Numbers from the literature, not from your body. They change only between sessions — mid-session you would be measuring a moving target. Every measurement window remembers which values it was made with.'),
    'dev.locked': _sk_en(
        'Relácia beží, takže sa nedajú meniť. Vypni senzor tepu a otvor to znova.',
        'A session is running, so these are locked. Turn the sensor off and reopen this.'),
    'dev.param.stress_threshold': _sk_en('Prah záťaže', 'Load threshold'),
    'dev.param.stress_hold_s': _sk_en('Zotrvanie nad prahom', 'Time above threshold'),
    'dev.param.dip_grace_s': _sk_en('Tolerovaný prepad', 'Tolerated dip'),
    'dev.param.pause_s': _sk_en('Prah pauzy', 'Pause threshold'),
    'dev.param.max_wait_s': _sk_en('Najdlhšie čakanie', 'Longest wait'),
    'dev.param.away_s': _sk_en('Odchod od PC', 'Away from the PC'),
    'dev.param.min_gap_s': _sk_en(
        'Odstup medzi pripomienkami',
        'Gap between cues'),
    'dev.silent': _sk_en(
        'Podiel tichých pripomienok (0–1)',
        'Share of silent cues (0–1)'),
    'dev.reset': _sk_en('Východiskové', 'Defaults'),
    'dev.fire': _sk_en('Vystreliť teraz', 'Fire now'),
    'dev.windows': _sk_en('Posledné meracie okná', 'Last measurement windows'),
    'dev.windows_empty': _sk_en('Zatiaľ žiadne.', 'None yet.'),
    'dev.bad_number': _sk_en('Niektoré pole nie je číslo.', 'One of the fields is not a number.'),
    'dev.applied': _sk_en('Ladenie: hodnoty uložené, platia od ďalšej relácie.',
                          'Tuning: values saved, they apply from the next session.'),
})
_tr7('dev.title', 'チューニング', '调参', 'Настройка', 'Ajustes finos', 'Feinabstimmung', 'Réglage', 'Ajuste fino')
_tr7('dev.hint', '文献から来た数字で、あなたの体から来たものではない。変更できるのはセッションの合間だけ — 途中で変えると動く的を測ることになる。各測定ウィンドウはどの値で作られたか覚えている。', '这些数字来自文献，不是来自你的身体。只能在两次记录之间修改——中途修改就是在测一个移动的目标。每个测量窗口都记得自己是用哪些值生成的。', 'Числа из литературы, а не из твоего тела. Меняются только между сессиями — посреди сессии пришлось бы мерить движущуюся мишень. Каждое измерительное окно помнит, с какими значениями возникло.', 'Números de la literatura, no de tu cuerpo. Solo se cambian entre sesiones: a mitad estarías midiendo un blanco en movimiento. Cada ventana de medición recuerda con qué valores se hizo.', 'Zahlen aus der Literatur, nicht aus deinem Körper. Änderbar nur zwischen Sitzungen — mittendrin würdest du ein bewegtes Ziel messen. Jedes Messfenster merkt sich, mit welchen Werten es entstand.', 'Des chiffres tirés de la littérature, pas de ton corps. Modifiables seulement entre les séances — en cours, tu mesurerais une cible mouvante. Chaque fenêtre de mesure retient avec quelles valeurs elle a été faite.', 'Números da literatura, não do seu corpo. Só mudam entre sessões — no meio de uma, você estaria medindo um alvo em movimento. Cada janela de medição lembra com que valores foi feita.')
_tr7('dev.locked', 'セッション中なので変更できない。心拍センサーを切ってから開き直して。', '记录进行中，无法修改。请关闭心率传感器后重新打开。', 'Сессия идёт, менять нельзя. Выключи датчик пульса и открой заново.', 'Hay una sesión en curso, no se pueden cambiar. Apaga el sensor y vuelve a abrir esto.', 'Eine Sitzung läuft, daher gesperrt. Schalte den Sensor aus und öffne das erneut.', 'Une séance est en cours, c’est verrouillé. Coupe le capteur et rouvre ceci.', 'Há uma sessão em andamento, por isso está bloqueado. Desative o sensor e abra isto de novo.')
_tr7('dev.param.stress_threshold', '負荷のしきい値', '负荷阈值', 'Порог нагрузки', 'Umbral de carga', 'Last-Schwelle', 'Seuil de charge', 'Limiar de carga')
_tr7('dev.param.stress_hold_s', 'しきい値を超えている時間', '超过阈值的持续时间', 'Время над порогом', 'Tiempo por encima', 'Zeit über der Schwelle', 'Temps au-dessus du seuil', 'Tempo acima do limiar')
_tr7('dev.param.dip_grace_s', '許容する落ち込み', '容许的回落', 'Допустимый провал', 'Caída tolerada', 'Tolerierter Einbruch', 'Creux toléré', 'Queda tolerada')
_tr7('dev.param.pause_s', '休みのしきい値', '停顿阈值', 'Порог паузы', 'Umbral de pausa', 'Pausen-Schwelle', 'Seuil de pause', 'Limiar de pausa')
_tr7('dev.param.max_wait_s', '最長の待ち時間', '最长等待', 'Максимум ожидания', 'Espera máxima', 'Längste Wartezeit', 'Attente maximale', 'Espera máxima')
_tr7('dev.param.away_s', '席を外した', '离开电脑', 'Отход от ПК', 'Se alejó del PC', 'Vom PC weg', 'Absent du PC', 'Longe do PC')
_tr7('dev.param.min_gap_s', '合図の間隔', '提示间隔', 'Промежуток между подсказками', 'Intervalo entre avisos', 'Abstand zwischen Hinweisen', 'Intervalle entre rappels', 'Intervalo entre avisos')
_tr7('dev.silent', '音を出さない合図の割合（0〜1）', '静默提示比例（0–1）', 'Доля тихих подсказок (0–1)', 'Proporción de avisos silenciosos (0–1)', 'Anteil stiller Hinweise (0–1)', 'Part de rappels silencieux (0–1)', 'Proporção de avisos silenciosos (0–1)')
_tr7('dev.reset', '既定値', '默认值', 'По умолчанию', 'Por defecto', 'Standardwerte', 'Valeurs par défaut', 'Padrões')
_tr7('dev.fire', '今すぐ出す', '立即触发', 'Выстрелить сейчас', 'Lanzar ahora', 'Jetzt auslösen', 'Déclencher maintenant', 'Disparar agora')
_tr7('dev.windows', '直近の測定ウィンドウ', '最近的测量窗口', 'Последние измерительные окна', 'Últimas ventanas de medición', 'Letzte Messfenster', 'Dernières fenêtres de mesure', 'Últimas janelas de medição')
_tr7('dev.windows_empty', 'まだない。', '还没有。', 'Пока нет.', 'Todavía ninguna.', 'Noch keine.', 'Aucune pour l’instant.', 'Ainda nenhuma.')
_tr7('dev.bad_number', 'どれかの欄が数字ではない。', '有一个字段不是数字。', 'Одно из полей не число.', 'Uno de los campos no es un número.', 'Eines der Felder ist keine Zahl.', 'L’un des champs n’est pas un nombre.', 'Um dos campos não é um número.')
_tr7('dev.applied', 'チューニング：保存した。次のセッションから有効。', '调参：已保存，从下次记录开始生效。', 'Настройка: значения сохранены, действуют со следующей сессии.', 'Ajustes: guardados, se aplican desde la próxima sesión.', 'Feinabstimmung: gespeichert, gilt ab der nächsten Sitzung.', 'Réglage : enregistré, effectif dès la prochaine séance.', 'Ajuste fino: salvo, vale a partir da próxima sessão.')
_tr7('session.end.title', '{time} プレイした。', '你玩了 {time}。', 'За тобой {time} игры.', 'Jugaste {time}.', 'Du hast {time} gespielt.', 'Tu as joué {time}.', 'Você jogou por {time}.')
_tr7('session.end.cues', '{n} 回、合図を出しました。', '我提醒了你 {n} 次。', 'Я подала знак {n}×.', 'Te he avisado {n}×.', 'Ich habe mich {n}× gemeldet.', 'Je me suis manifestée {n}×.', 'Avisei {n}×.')
_tr7('session.end.none_short', '負荷は上がりましたが、連続で最長 {najdlhsie} 秒 — {treba} 秒必要です。', '负荷确实升高了，但最长连续 {najdlhsie} 秒——我需要 {treba} 秒。', 'Нагрузка поднималась, но дольше всего {najdlhsie} с подряд — нужно {treba} с.', 'La carga sí subió, pero lo más largo fueron {najdlhsie} s seguidos: necesito {treba} s.', 'Die Belastung stieg, aber am längsten {najdlhsie} s am Stück — ich brauche {treba} s.', 'La charge est montée, mais au plus long {najdlhsie} s d’affilée — il m’en faut {treba}.', 'A carga subiu, mas no máximo {najdlhsie} s seguidos — preciso de {treba} s.')
_tr7('session.end.cues_none', '今日は一度も声をかけなかった。', '今天我一次也没出声。', 'Сегодня я не подала голос ни разу.', 'Hoy no hablé ni una vez.', 'Heute habe ich kein einziges Mal gesprochen.', 'Aujourd’hui je n’ai pas parlé une seule fois.', 'Hoje não falei nem uma vez.')
_tr7('session.context.body_question', '体に入っていたものはありますか？', '你摄入了以下哪些？', 'Было ли что-то из этого в организме?', '¿Habías tomado algo de esto?', 'Hattest du etwas davon intus?', 'Avais-tu pris l’un de ces produits ?', 'Você tinha algum destes no corpo?')
_tr7('session.context.caffeine', 'カフェイン / エナジードリンク', '咖啡因 / 能量饮料', 'кофеин / энергетик', 'cafeína / bebida energética', 'Koffein / Energydrink', 'caféine / boisson énergisante', 'cafeína / bebida energética')
_tr7('session.context.alcohol', 'アルコール', '酒精', 'алкоголь', 'alcohol', 'Alkohol', 'alcool', 'álcool')
_tr7('session.context.nicotine', 'ニコチン', '尼古丁', 'никотин', 'nicotina', 'Nikotin', 'nicotine', 'nicotina')
_tr7('session.context.question', 'こういうことはあった？', '有发生这些情况吗？', 'Что-то из этого было?', '¿Pasó algo de esto?', 'Ist etwas davon passiert?', 'Est-ce que quelque chose de tout ça est arrivé ?', 'Aconteceu alguma destas coisas?')
_tr7('session.context.why', '話すと呼吸が変わって心拍が上がる。これがないと、そういう夜は「合図が効かない」ように見えてしまう — 実際は関係ないのに。', '说话时呼吸会变、心率会升高。没有这一项，这样的夜晚看起来就像提示没用——其实毫无关系。', 'Когда говоришь, меняется дыхание и пульс растёт. Без этого такой вечер выглядел бы так, будто подсказки не работают — хотя дело вообще не в них.', 'Cuando hablas cambia tu respiración y sube el pulso. Sin esto, esa noche parecería que los avisos no sirven, cuando no tienen nada que ver.', 'Beim Sprechen ändert sich die Atmung und der Puls steigt. Ohne das sähe so ein Abend aus, als würden die Hinweise nichts bringen — obwohl es gar nicht an ihnen liegt.', 'Quand tu parles, ta respiration change et ton pouls monte. Sans ça, une telle soirée donnerait l’impression que les rappels ne servent à rien — alors qu’ils n’y sont pour rien.', 'Quando você fala, a respiração muda e o pulso sobe. Sem isto, uma noite dessas pareceria que os avisos não funcionam — quando não têm nada a ver.')
_tr7('session.context.call', '誰かと通話した', '在语音通话', 'созвон с кем-то', 'estuve en una llamada', 'war im Call', 'j’étais en vocal', 'estive numa chamada')
_tr7('session.context.laugh', '笑っていた', '一直在笑', 'смех', 'me estuve riendo', 'habe gelacht', 'j’ai ri', 'dei risada')
_tr7('session.context.grind', '作業ゲー', '刷本', 'гринд', 'grindeo', 'Grind', 'grind', 'grind')
_tr7('session.context.competitive', 'ランク・競技', '排位', 'соревновательное', 'competitivo', 'kompetitiv', 'compétitif', 'competitivo')
_tr7('session.context.chill', 'まったり', '休闲', 'чилл', 'chill', 'entspannt', 'tranquille', 'chill')
_tr7('session.end.skip', 'スキップ', '跳过', 'Пропустить', 'Omitir', 'Überspringen', 'Passer', 'Ignorar')
_tr7('data.title', 'あなたのデータ', '你的数据', 'Твои данные', 'Tus datos', 'Deine Daten', 'Tes données', 'Os seus dados')
_tr7('data.delete.btn', '履歴を削除', '删除历史', 'Удалить историю', 'Borrar historial', 'Verlauf löschen', 'Supprimer l’historique', 'Apagar histórico')
_tr7('data.delete.title', '履歴を削除する？', '删除历史？', 'Удалить историю?', '¿Borrar historial?', 'Verlauf löschen?', 'Supprimer l’historique ?', 'Apagar histórico?')
_tr7('data.delete.intro', 'これが消える。元には戻せない：', '以下内容将被删除，且无法恢复：', 'Будет удалено, и вернуть это нельзя:', 'Se borrará esto y no se puede deshacer:', 'Das wird gelöscht und lässt sich nicht rückgängig machen:', 'Ceci sera supprimé et ne pourra pas être récupéré :', 'Isto será apagado e não pode ser recuperado:')
_tr7('data.delete.sessions', 'セッション履歴', '记录历史', 'история сессий', 'historial de sesiones', 'Sitzungsverlauf', 'historique des séances', 'histórico de sessões')
_tr7('data.delete.windows', '測定ウィンドウ', '测量窗口', 'измерительные окна', 'ventanas de medición', 'Messfenster', 'fenêtres de mesure', 'janelas de medição')
_tr7('data.delete.insights', '分析の所見', '分析结论', 'наблюдения из анализа', 'observaciones del análisis', 'Beobachtungen aus der Analyse', 'observations de l’analyse', 'observações da análise')
_tr7('data.delete.logs', 'ログ', '日志', 'логи', 'registros', 'Logs', 'journaux', 'registros')
_tr7('data.delete.open_session', '進行中のセッション', '进行中的记录', 'текущая сессия', 'sesión en curso', 'laufende Sitzung', 'séance en cours', 'sessão em andamento')
_tr7('data.delete.empty', '（空）', '（空）', '(пусто)', '(vacío)', '(leer)', '(vide)', '(vazio)')
_tr7('data.delete.done', '削除した（{n} 件）。', '已删除（{n} 项）。', 'Удалено ({n}).', 'Borrado ({n} elementos).', 'Gelöscht ({n} Einträge).', 'Supprimé ({n} éléments).', 'Apagado ({n} itens).')
_tr7('data.export.done', '保存した：{path}', '已保存：{path}', 'Сохранено: {path}', 'Guardado: {path}', 'Gespeichert: {path}', 'Enregistré : {path}', 'Salvo: {path}')
_tr7('data.import.btn', 'ファイルから読み込む', '从文件导入', 'Импортировать из файла', 'Importar desde un archivo', 'Aus Datei importieren', 'Importer depuis un fichier', 'Importar de um arquivo')
_tr7('data.import.title', 'データを読み込む', '导入数据', 'Импорт данных', 'Importar datos', 'Daten importieren', 'Importer des données', 'Importar dados')
_tr7('data.import.found', 'ファイルにセッション {sessions} 件、測定ウィンドウ {windows} 件。', '文件中有 {sessions} 条记录和 {windows} 个测量窗口。', 'В файле {sessions} сессий и {windows} измерительных окон.', 'El archivo tiene {sessions} sesiones y {windows} ventanas de medición.', 'Die Datei enthält {sessions} Sitzungen und {windows} Messfenster.', 'Le fichier contient {sessions} séances et {windows} fenêtres de mesure.', 'O arquivo tem {sessions} sessões e {windows} janelas de medição.')
_tr7('data.import.dropped', '{n} 件は読めず、飛ばした。', '有 {n} 条无法读取，已跳过。', '{n} записей не удалось прочитать, они пропущены.', '{n} registros no se pudieron leer y se omitieron.', '{n} Einträge konnten nicht gelesen werden und wurden übersprungen.', '{n} enregistrements illisibles ont été ignorés.', '{n} registros não puderam ser lidos e foram ignorados.')
_tr7('data.import.merge', '自分のものと統合', '与我的合并', 'Объединить с моими', 'Combinar con los míos', 'Mit meinen zusammenführen', 'Fusionner avec les miens', 'Juntar aos meus')
_tr7('data.import.replace', '自分のものを置き換える', '替换我的', 'Заменить мои', 'Reemplazar los míos', 'Meine ersetzen', 'Remplacer les miens', 'Substituir os meus')
_tr7('data.import.done', '読み込んだ：セッション {sessions} 件、ウィンドウ {windows} 件。', '已导入：{sessions} 条记录，{windows} 个窗口。', 'Импортировано: {sessions} сессий, {windows} окон.', 'Importado: {sessions} sesiones, {windows} ventanas.', 'Importiert: {sessions} Sitzungen, {windows} Fenster.', 'Importé : {sessions} séances, {windows} fenêtres.', 'Importado: {sessions} sessões, {windows} janelas.')
_tr7('data.import.not_json', 'これは有効な JSON ファイルではない。', '这不是有效的 JSON 文件。', 'Это не корректный файл JSON.', 'Este no es un archivo JSON válido.', 'Das ist keine gültige JSON-Datei.', 'Ce n’est pas un fichier JSON valide.', 'Este não é um arquivo JSON válido.')
_tr7('data.import.unreadable', 'ファイルを読めない。', '无法读取该文件。', 'Файл не читается.', 'No se puede leer el archivo.', 'Die Datei lässt sich nicht lesen.', 'Le fichier ne peut pas être lu.', 'Não foi possível ler o arquivo.')
_tr7('data.import.foreign', 'このファイルは Zanshin の書き出しではない。', '这个文件不是 Zanshin 的导出文件。', 'Этот файл не является экспортом из Zanshin.', 'Este archivo no es una exportación de Zanshin.', 'Diese Datei ist kein Export aus Zanshin.', 'Ce fichier n’est pas un export de Zanshin.', 'Este arquivo não é uma exportação do Zanshin.')
_tr7('data.import.newer', 'ファイルは新しいバージョンのもの。アプリを更新して。', '文件来自更新的版本，请更新应用。', 'Файл из более новой версии приложения. Обнови приложение.', 'El archivo es de una versión más nueva. Actualiza la app.', 'Die Datei stammt aus einer neueren Version. Aktualisiere die App.', 'Le fichier vient d’une version plus récente. Mets l’app à jour.', 'O arquivo é de uma versão mais recente. Atualize o app.')
_tr7('data.import.empty', 'ファイルに使える記録がない。', '文件中没有可用的记录。', 'В файле нет пригодных записей.', 'El archivo no contiene registros utilizables.', 'Die Datei enthält keine brauchbaren Einträge.', 'Le fichier ne contient aucun enregistrement utilisable.', 'O arquivo não contém registros utilizáveis.')
_tr7('log.cue_delivered', '合図を出しました：{label}', '我提醒了你：{label}', 'Я подала знак: {label}', 'He avisado: {label}', 'Ich habe mich gemeldet: {label}', 'Je me suis manifestée : {label}', 'Eu avisei: {label}')
_tr7('log.game_lang', 'ゲーム中の言語：{lang}', '游戏中的语言：{lang}', 'Язык в игре: {lang}', 'Idioma en el juego: {lang}', 'Sprache im Spiel: {lang}', 'Langue en jeu : {lang}', 'Idioma no jogo: {lang}')


# --------------------------------------------------------------------------
# Added translations (final i18n) - strings really missing in 7 languages.
# Patches existing entries in STRINGS (does not change sk/en).
# --------------------------------------------------------------------------
# --- 0.3 batch 4: Today, main switch, side panel, empty states ---
# The main switch is one button with text (`dock.start` / `dock.stop`,
# rewritten above). The sentence "Klikni ▶ vlavo" (Click ▶ on the left)
# under it lost its meaning; only the one about why the bar breathes
# remained (`kamae.bar_hint`). The side panel has short labels for the
# watch and the magnifier too, and the "In game" page is called "Screen"
# in the Work world. `dnes.learning` is a quiet sentence while the app is
# learning the heart rate limit and the load threshold
# (`hr_stats.KRITICKY_MIN_RELACII` play sessions of at least 5 min) -
# {celkom} is always at least 2, so the noun after "z/of/из" has the same
# form in every language (genitive plural).
STRINGS.update({
    'kamae.bar_hint': _sk_en('Kým sledujem, pás dýcha — inak stojí.',
                             'While I’m watching, this bar breathes; otherwise it rests.'),
    'nav.watch': _sk_en('Hodinky', 'Watch'),
    'nav.search': _sk_en('Hľadať', 'Search'),
    'nav.vhre_work_short': _sk_en('Obrazovka', 'Screen'),
    'nav.vhre_work': _sk_en('Hodinky a obrazovka', 'Watch and screen'),
    'dnes.zones_empty': _sk_en('Pásma sa ukážu po prvej relácii s tepom.',
                               'Zones show up after your first session with heart rate.'),
    'dnes.learning': _sk_en(
        'Ešte ťa spoznávam — {n} z {celkom} herných relácií (každá aspoň 5 min)',
        'Still getting to know you — {n} of {celkom} play sessions (5+ min each)'),
    'kamae.port_busy': _sk_en('Port {port} je obsadený', 'Port {port} is busy'),
    'kamae.port_busy_sub': _sk_en(
        'Drží ho iný program — často OBS so zapnutým WebSocket serverom. Vypni ten '
        'server v OBS, alebo zmeň port v „{page} → {card}“ a to isté číslo '
        'zadaj v appke v telefóne.',
        'Another program is holding it — often OBS with its WebSocket server on. '
        'Switch that server off in OBS, or change the port in “{page} → {card}” '
        'and enter the same number in the phone app.'),
})
_tr7('kamae.bar_hint', '見守っている間は帯が呼吸し、それ以外は止まっています。', '我在关注时，这条带会呼吸；否则就静止。', 'Пока я наблюдаю, полоса дышит, иначе — замирает.', 'Mientras observo, la barra respira; si no, se queda quieta.', 'Solange ich beobachte, atmet die Leiste — sonst ruht sie.', 'Tant que j’observe, la barre respire ; sinon, elle reste immobile.', 'Enquanto observo, a barra respira; senão, fica parada.')
_tr7('nav.watch', '時計', '手表', 'Часы', 'Reloj', 'Uhr', 'Montre', 'Relógio')
_tr7('nav.search', '検索', '搜索', 'Поиск', 'Buscar', 'Suchen', 'Chercher', 'Buscar')
_tr7('nav.vhre_work_short', '画面', '屏幕', 'Экран', 'Pantalla', 'Bildschirm', 'Écran', 'Tela')
_tr7('nav.vhre_work', '時計と画面', '手表与屏幕', 'Часы и экран', 'Reloj y pantalla', 'Uhr und Bildschirm', 'Montre et écran', 'Relógio e tela')
_tr7('dnes.zones_empty', '心拍のある最初のセッションのあとに、ゾーンが表示されます。', '有心率的第一次记录之后，这里会显示区间。', 'Зоны появятся после первой сессии с пульсом.', 'Las zonas aparecerán tras tu primera sesión con pulso.', 'Die Zonen erscheinen nach deiner ersten Sitzung mit Puls.', 'Les zones apparaîtront après ta première séance avec le pouls.', 'As zonas aparecem depois da sua primeira sessão com pulso.')
_tr7('dnes.learning', 'まだあなたのことを学んでいます — ゲームセッション {celkom} 回のうち {n} 回（各5分以上）','我还在了解你——{celkom} 次游戏记录中已有 {n} 次（每次至少 5 分钟）', 'Я ещё знакомлюсь с тобой — {n} из {celkom} игровых сессий (каждая от 5 минут)', 'Todavía te estoy conociendo: {n} de {celkom} sesiones de juego (de al menos 5 min cada una)', 'Ich lerne dich noch kennen — {n} von {celkom} Spielsitzungen (je mindestens 5 Min.)', 'J’apprends encore à te connaître — {n} sur {celkom} séances de jeu (au moins 5 min chacune)', 'Ainda estou te conhecendo — {n} de {celkom} sessões de jogo (cada uma com pelo menos 5 min)')
_tr7('kamae.port_busy', 'ポート {port} が使用中です', '端口 {port} 被占用', 'Порт {port} занят', 'El puerto {port} está ocupado', 'Port {port} ist belegt', 'Le port {port} est occupé', 'A porta {port} está ocupada')
_tr7('kamae.port_busy_sub', '別のプログラムがこのポートを使っています。よくあるのは WebSocket サーバーをオンにした OBS です。OBS でそのサーバーをオフにするか、「{page}→{card}」でポートを変えて、同じ番号を電話のアプリにも入力してください。', '另一个程序占用了这个端口，常见的是开启了 WebSocket 服务器的 OBS。在 OBS 里关掉这个服务器，或在“{page}→{card}”中更改端口，并在手机应用里填入相同的号码。','Его держит другая программа — часто OBS с включённым WebSocket-сервером. Выключи этот сервер в OBS или смени порт в «{page} → {card}» и введи то же число в приложении на телефоне.', 'Otro programa lo está usando: a menudo OBS con su servidor WebSocket activado. Apaga ese servidor en OBS o cambia el puerto en «{page} → {card}» e introduce el mismo número en la app del móvil.', 'Ein anderes Programm belegt ihn — oft OBS mit eingeschaltetem WebSocket-Server. Schalte diesen Server in OBS aus oder ändere den Port unter „{page} → {card}“ und gib dieselbe Zahl in der Handy-App ein.', 'Un autre programme l’occupe — souvent OBS avec son serveur WebSocket activé. Désactive ce serveur dans OBS, ou change le port dans « {page} → {card} » et saisis le même numéro dans l’app du téléphone.', 'Outro programa está usando a porta — muitas vezes o OBS com o servidor WebSocket ligado. Desligue esse servidor no OBS ou mude a porta em “{page} → {card}” e digite o mesmo número no app do celular.')


# --- 0.3 batch 4: app dialogs, History, Settings, questionnaire ---
# App windows instead of system ones (`ui_kit.notify` / `confirm` /
# `choose`), a dialog on the first × (two clear buttons instead of
# Yes/No), the labels of the Consistency grid (months and days by the
# app's language, not Windows') and a sentence in the questionnaire when
# the game filled the whole screen.
STRINGS.update({
    'dialog.ok': _sk_en('OK', 'OK'),
    'tray.keep_running': _sk_en('Nechať bežať v lište', 'Keep running in the tray'),
    'tray.quit_app': _sk_en('Ukončiť Zanshin', 'Quit Zanshin'),
    'profile.delete_btn': _sk_en('Odstrániť profil', 'Delete profile'),
    # 12 month abbreviations and 7 days (Monday first), space-separated
    'history.grid_months': _sk_en(
        'jan feb mar apr máj jún júl aug sep okt nov dec',
        'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'),
    'history.grid_weekdays': _sk_en('po ut st št pi so ne',
                                    'Mon Tue Wed Thu Fri Sat Sun'),
    'session.end.fullscreen_note': _sk_en(
        'Hra zaberala celú obrazovku — ak obrázky nebolo vidieť, prepni ju na „Bez okrajov / Borderless“. Hlas funguje aj tak.',
        'The game filled the whole screen — if the pictures didn’t show, switch it to “Borderless”. The voice works either way.'),
})
_tr7('dialog.ok', 'OK', '确定', 'ОК', 'Aceptar', 'OK', 'OK', 'OK')
_tr7('tray.keep_running', 'トレイで動かし続ける', '在托盘中继续运行', 'Оставить работать в трее', 'Seguir en la bandeja', 'Im Infobereich weiterlaufen', 'Rester dans la zone de notification', 'Continuar na bandeja')
_tr7('tray.quit_app', 'Zanshin を終了', '退出 Zanshin', 'Выйти из Zanshin', 'Salir de Zanshin', 'Zanshin beenden', 'Quitter Zanshin', 'Sair do Zanshin')
_tr7('profile.delete_btn', 'プロファイルを削除', '删除配置文件', 'Удалить профиль', 'Eliminar perfil', 'Profil löschen', 'Supprimer le profil', 'Excluir perfil')
_tr7('history.grid_months', '1月 2月 3月 4月 5月 6月 7月 8月 9月 10月 11月 12月', '1月 2月 3月 4月 5月 6月 7月 8月 9月 10月 11月 12月', 'янв фев мар апр май июн июл авг сен окт ноя дек', 'ene feb mar abr may jun jul ago sep oct nov dic', 'Jan Feb Mär Apr Mai Jun Jul Aug Sep Okt Nov Dez', 'janv. févr. mars avr. mai juin juil. août sept. oct. nov. déc.', 'jan fev mar abr mai jun jul ago set out nov dez')
_tr7('history.grid_weekdays', '月 火 水 木 金 土 日', '一 二 三 四 五 六 日', 'пн вт ср чт пт сб вс', 'lu ma mi ju vi sá do', 'Mo Di Mi Do Fr Sa So', 'lun mar mer jeu ven sam dim', 'seg ter qua qui sex sáb dom')
_tr7('session.end.fullscreen_note', 'ゲームが画面全体を占めていました — 画像が見えなかったら「ボーダーレス / Borderless」に切り替えて。声はどちらでも届きます。', '游戏占满了整个屏幕——如果没看到图片，请把它切换到“无边框 / Borderless”。声音照常可用。', 'Игра занимала весь экран — если картинок не было видно, переключи её в «Без рамки / Borderless». Голос работает в любом случае.', 'El juego ocupaba toda la pantalla: si no se veían las imágenes, cámbialo a «Sin bordes / Borderless». La voz funciona igual.', 'Das Spiel hat den ganzen Bildschirm gefüllt — waren die Bilder nicht zu sehen, stell es auf „Randlos / Borderless“ um. Die Stimme funktioniert so oder so.', 'Le jeu occupait tout l’écran — si les images ne s’affichaient pas, passe-le en « Sans bordure / Borderless ». La voix fonctionne de toute façon.', 'O jogo ocupava a tela inteira — se as imagens não apareceram, mude-o para “Sem bordas / Borderless”. A voz funciona de qualquer jeito.')

# --- 0.3 batch 4: logic and edge cases (shortcut, PC sleep, data, voice, VPN) ---
# The "not now" shortcut (clash with AltGr, choice in Settings -> General,
# a sentence in the tour), a session split after the PC went to sleep,
# deleting one session in History, a session that could not be saved,
# the data folder, the history cap on import, natural voice errors, the
# world during a session, VPN/virtual adapters and a second "Quit" over
# the questionnaire.
# Counts are always "{n} min" or "(count: {n})" - so the form of the noun
# does not change with the number in any language. `kamae.snoozed_sub`
# (with {combo}) is rewritten directly at its definition below (the
# "24. 9." block).
STRINGS.update({
    'settings.snooze_hotkey_title': _sk_en('Skratka „Teraz nie“', 'The “Not now” shortcut'),
    'settings.snooze_hotkey': _sk_en('Klávesová skratka', 'Keyboard shortcut'),
    'settings.snooze_hotkey_sub': _sk_en(
        '{combo} ma stíši na {minutes} min a tep merám ďalej. Platí v každom okne, aj v hre.',
        '{combo} quiets me for {minutes} min while I keep measuring your heart rate. '
        'It works in every window, in-game too.'),
    'settings.snooze_hotkey_off_sub': _sk_en(
        'Skratka je vypnutá. „Teraz nie“ nájdeš v ponuke ikony v lište (pravý klik).',
        'The shortcut is off. “Not now” is in the tray icon’s menu (right-click).'),
    'settings.snooze_hotkey_taken': _sk_en(
        '{combo} teraz drží iný program, takže nefunguje. Vyber inú skratku alebo použi '
        '„Teraz nie“ v ponuke ikony v lište.',
        'Another program is holding {combo} right now, so it doesn’t work. Pick another '
        'shortcut, or use “Not now” in the tray icon’s menu.'),
    'settings.snooze_hotkey_none': _sk_en('Vypnutá', 'Off'),
    'settings.snooze_hotkey_types': _sk_en('{combo} (píše „{char}“)', '{combo} (types “{char}”)'),
    'log.hotkey_layout_swapped': _sk_en(
        '{combo} by ti brala písmeno „{char}“ (AltGr je to isté ako Ctrl+Alt), preto je '
        '„Teraz nie“ na {new}. Zmeniť to môžeš v Nastaveniach → Všeobecné.',
        '{combo} would take away the letter “{char}” from your typing (AltGr is the same '
        'as Ctrl+Alt), so “Not now” is on {new} instead. You can change it in '
        'Settings → General.'),
    'log.hotkey_layout_off': _sk_en(
        '{combo} by ti brala písmeno „{char}“ (AltGr je to isté ako Ctrl+Alt), preto '
        'skratku nezapínam. „Teraz nie“ nájdeš v ponuke ikony v lište.',
        '{combo} would take away the letter “{char}” from your typing (AltGr is the same '
        'as Ctrl+Alt), so I’m leaving the shortcut off. “Not now” is in the tray icon’s menu.'),
    'log.hotkey_off': _sk_en(
        'Skratka „Teraz nie“ je vypnutá. Stíšiť ma môžeš v ponuke ikony v lište.',
        'The “Not now” shortcut is off. You can still quiet me from the tray icon’s menu.'),
    'kamae.snoozed_sub_tray': _sk_en(
        '„Teraz nie“ platí do {until} — dovtedy sa neozvem, tep však merám ďalej. Skôr to '
        'zrušíš v ponuke ikony v lište.',
        '“Not now” holds until {until} — I won’t speak up till then, but I keep measuring '
        'your heart rate. End it sooner from the tray icon’s menu.'),
    'tour.triggers.snooze': _sk_en(
        'Keď sa ozvem v zlej chvíli, stlač {combo} — pol hodiny budem ticho a tep merám ďalej.',
        'If I speak up at a bad moment, press {combo} — I’ll stay quiet for half an hour '
        'and keep measuring.'),
    'tour.triggers.snooze_tray': _sk_en(
        'Keď sa ozvem v zlej chvíli, daj „Teraz nie“ v ponuke ikony v lište — pol hodiny '
        'budem ticho a tep merám ďalej.',
        'If I speak up at a bad moment, pick “Not now” in the tray icon’s menu — I’ll stay '
        'quiet for half an hour and keep measuring.'),
    'log.session_split_sleep': _sk_en(
        'Počítač asi spal ({min} min). Reláciu som uzavrela tam, kde spánok začal, a začala '
        'som novú.',
        'The PC seems to have slept ({min} min). I closed the session where the sleep began '
        'and started a new one.'),
    'log.session_split_sleep_end': _sk_en(
        'Počítač asi spal ({min} min). Reláciu som uzavrela tam, kde spánok začal.',
        'The PC seems to have slept ({min} min). I closed the session where the sleep began.'),
    'history.delete_session.btn': _sk_en('Zmazať túto reláciu', 'Delete this session'),
    'history.delete_session.title': _sk_en('Zmazať reláciu?', 'Delete the session?'),
    'history.delete_session.body': _sk_en(
        'Zmaže sa relácia z {date} ({duration}) aj s jej meracími oknami a späť sa to vrátiť '
        'nedá. Postrehy potom prepočítam bez nej.',
        'The session from {date} ({duration}) will be deleted along with its measurement '
        'windows, and this cannot be undone. I’ll then recompute the insights without it.'),
    'history.delete_session.failed': _sk_en(
        'Reláciu sa nepodarilo zmazať — história sa nedala prečítať ani zapísať.',
        'Couldn’t delete the session — the history couldn’t be read or written.'),
    'log.session_deleted': _sk_en('Zmazala som reláciu z {date}.',
                                  'I deleted the session from {date}.'),
    'data.delete.export_first': _sk_en('Najprv exportovať…', 'Export first…'),
    'data.delete.stop_first': _sk_en(
        'Najprv zastav sledovanie — bežiaca relácia by sa po zmazaní znova uložila.',
        'Stop watching first — the running session would save itself again after the delete.'),
    'data.delete.pending_session': _sk_en('relácie, ktoré sa nepodarilo uložiť',
                                          'sessions that couldn’t be saved'),
    'session.save_failed.title': _sk_en('Relácia sa neuložila', 'The session wasn’t saved'),
    'log.hr_session_save_failed': _sk_en(
        'Reláciu sa nepodarilo uložiť ({err}). Odložila som ju bokom a do histórie ju doplním '
        'najneskôr pri ďalšom spustení.',
        'Couldn’t save the session ({err}). I set it aside and will add it to the history '
        'the next time the app starts, if not sooner.'),
    'log.hr_session_save_failed_lost': _sk_en(
        'Reláciu sa nepodarilo uložiť ({err}) a nedala sa ani odložiť bokom — skontroluj, '
        'či je na disku miesto a či priečinok s dátami nie je zamknutý.',
        'Couldn’t save the session ({err}), and couldn’t set it aside either — check that '
        'the disk has free space and the data folder isn’t locked.'),
    # The rule is `hr_stats.je_ulozitelna`: at least 60 s AND at least 10
    # heart rate values. The line goes out when the session lasted a minute,
    # but fewer values arrived (0.3 batch 4b) - "not even a minute of heart
    # rate" claimed a different rule from the one that applies.
    'log.hr_session_no_data': _sk_en(
        'Relácia sa neuložila — prišlo menej než 10 hodnôt tepu. Ukladám relácie, ktoré '
        'trvajú aspoň minútu a majú aspoň 10 hodnôt tepu.',
        'The session wasn’t saved — fewer than 10 heart-rate readings came in. I save '
        'sessions that last at least a minute and have at least 10 readings.'),
    'log.hr_session_pending_saved': _sk_en(
        'Doplnila som do histórie reláciu z {time}, ktorá sa minule nedala uložiť.',
        'I added the session from {time} to the history — it couldn’t be saved last time.'),
    'data.open_folder.btn': _sk_en('Otvoriť priečinok s dátami', 'Open the data folder'),
    'data.open_folder.failed': _sk_en('Priečinok s dátami sa nepodarilo otvoriť.',
                                      'Couldn’t open the data folder.'),
    'data.import.limit': _sk_en(
        'História pojme najviac {max} relácií, preto najstaršie vypadli (počet: {n}). Tvoje '
        'pôvodné sú v zálohe a importované ostávajú v importovanom súbore.',
        'The history holds at most {max} sessions, so the oldest were dropped (count: {n}). '
        'Your originals are in the backup, and the imported ones stay in the imported file.'),
    'data.import.backup_where': _sk_en('Nájdeš ich cez „Otvoriť priečinok s dátami“.',
                                       'You’ll find them via “Open the data folder”.'),
    # A permanent refusal is usually an outdated edge-tts in this version of
    # Zanshin (since November 2026 Microsoft refuses older versions, HTTP
    # 403). Since "Update voice" (0.3) the sentence first recommends that
    # button (it is right under it, the name exactly as on it -
    # `edge.update.btn`) and only then a new release from the official
    # GitHub, without a URL.
    'edge.partial_refused': _sk_en(
        '! hlas má len {ok}/{total} pripomienok — služba Microsoftu požiadavku odmietla. '
        'Najprv klikni nižšie na „Aktualizovať hlas“. Ak to nepomôže, táto verzia '
        'Zanshinu je asi zastaraná — novú nájdeš na oficiálnom GitHube (Releases); '
        'dovtedy môžeš prepnúť Zdroj hlasu na Windows.',
        '! only {ok}/{total} cues have their voice — Microsoft’s voice service refused the '
        'request. First click “Update voice” below. If that doesn’t help, this Zanshin '
        'version is probably outdated — get the new one from the official GitHub '
        '(Releases); until then you can switch Voice source to Windows.'),
    'edge.partial_other': _sk_en(
        '! hlas má len {ok}/{total} pripomienok — príprava zlyhala. Skús to znova.',
        '! only {ok}/{total} cues have their voice — preparing it failed. Try again.'),
    # The button is not repeated ("try again with the Try again button")
    # and {page} is the path the player really sees - Settings → Sound (0.3
    # batch 4b, `AudioMixin._edge_priprava_zlyhala`).
    'log.edge_failed_offline': _sk_en(
        'Prirodzený hlas sa nepodarilo pripraviť pre všetky pripomienky — služba Microsoftu '
        'je teraz nedostupná (internet alebo DNS). Zvyšok povie hlas z Windows. Keď '
        'nesledujem, klikni na „{retry}“ na stránke {page} alebo použi Ctrl+K → „{cmd}“.',
        'I couldn’t prepare the natural voice for every cue — Microsoft’s service can’t be '
        'reached right now (internet or DNS). The Windows voice covers the rest. While I’m '
        'not watching, click “{retry}” on the {page} page or use Ctrl+K → “{cmd}”.'),
    'log.edge_failed_refused': _sk_en(
        'Prirodzený hlas sa nepodarilo pripraviť pre všetky pripomienky — hlasová služba '
        'Microsoftu požiadavku odmietla. Keď nesledujem, klikni najprv na „Aktualizovať '
        'hlas“ na stránke {page}. Ak to nepomôže, táto verzia Zanshinu je asi zastaraná — '
        'novú nájdeš na oficiálnom GitHube (Releases); dovtedy zvyšok povie hlas z Windows, '
        'alebo prepni Zdroj hlasu na Windows. Znova to skúsiš cez „{retry}“ tamtiež alebo '
        'Ctrl+K → „{cmd}“.',
        'I couldn’t prepare the natural voice for every cue — Microsoft’s voice service '
        'refused the request. While I’m not watching, first click “Update voice” on the '
        '{page} page. If that doesn’t help, this Zanshin version is probably outdated — get '
        'the new one from the official GitHub (Releases); until then the Windows voice '
        'covers the rest, or switch Voice source to Windows. For another attempt, use '
        '“{retry}” there or Ctrl+K → “{cmd}”.'),
    'log.edge_failed_other': _sk_en(
        'Prirodzený hlas sa nepodarilo pripraviť pre všetky pripomienky ({err}). Zvyšok '
        'povie hlas z Windows. Keď nesledujem, klikni na „{retry}“ na stránke {page} alebo '
        'použi Ctrl+K → „{cmd}“.',
        'I couldn’t prepare the natural voice for every cue ({err}). The Windows voice '
        'covers the rest. While I’m not watching, click “{retry}” on the {page} page or '
        'use Ctrl+K → “{cmd}”.'),
    'log.world_switch_session': _sk_en(
        'Bežiaca relácia ostáva vo svete {world} — {new} platí od ďalšieho spustenia sledovania.',
        'The running session stays in {world} — {new} applies from the next time you start '
        'watching.'),
    # the label stands by the ADDRESS (adresa = feminine gender), 0.3 batch 4b
    'hr.ip_virtual': _sk_en('(VPN/virtuálna)', '(VPN/virtual)'),
    'hr.ip_virtual_note': _sk_en(
        'Táto adresa patrí VPN alebo virtuálnemu adaptéru — telefón sa na ňu väčšinou '
        'nedostane. Máš zapnutú VPN? Vypni ju alebo v nej povoľ prístup do lokálnej siete.',
        'This address belongs to a VPN or virtual adapter — the phone usually can’t reach '
        'it. Using a VPN? Turn it off, or allow local network access in it.'),
    'settings.hr_ip_virtual_note': _sk_en(
        'Adresa v poli patrí VPN alebo virtuálnemu adaptéru — telefón sa na ňu väčšinou '
        'nedostane. Nechaj radšej 0.0.0.0.',
        'The address in this field belongs to a VPN or virtual adapter — the phone usually '
        'can’t reach it. Better leave 0.0.0.0.'),
    'log.quit_questionnaire_saved': _sk_en(
        'Pri ukončení som uložila odpovede, ktoré už v dotazníku boli vyplnené.',
        'On quitting, I saved the answers already filled in on the questionnaire.'),
    'log.quit_questionnaire_skipped': _sk_en(
        'Pri ukončení som zavrela prázdny dotazník — relácia ostala uložená bez odpovedí.',
        'On quitting, I closed the empty questionnaire — the session stays saved without '
        'answers.'),
})
_tr7('settings.snooze_hotkey_title', '「今はいい」のショートカット', '“现在不要”快捷键', 'Сочетание клавиш «Не сейчас»', 'Atajo de «Ahora no»', 'Kürzel für „Jetzt nicht“', 'Raccourci « Pas maintenant »', 'Atalho do “Agora não”')
_tr7('settings.snooze_hotkey', 'ショートカットキー', '快捷键', 'Сочетание клавиш', 'Atajo de teclado', 'Tastenkürzel', 'Raccourci clavier', 'Atalho de teclado')
_tr7('settings.snooze_hotkey_sub', '{combo} で {minutes} 分間静かにします。心拍の計測は続けます。ゲーム中も含め、どのウィンドウでも使えます。', '{combo} 让我安静 {minutes} 分钟，心率照常测量。在任何窗口里都有效，游戏中也是。', '{combo} заставит меня молчать {minutes} мин, а пульс я продолжу измерять. Работает в любом окне, и в игре тоже.', '{combo} me silencia {minutes} min y sigo midiendo tu pulso. Funciona en cualquier ventana, también en el juego.', '{combo} lässt mich {minutes} Min. schweigen, den Puls messe ich weiter. Es wirkt in jedem Fenster, auch im Spiel.', '{combo} me fait taire {minutes} min, et je continue à mesurer ton pouls. Ça marche dans toutes les fenêtres, en jeu aussi.', '{combo} me silencia por {minutes} min e continuo medindo o seu pulso. Funciona em qualquer janela, também no jogo.')
_tr7('settings.snooze_hotkey_off_sub', 'ショートカットはオフです。「今はいい」はトレイアイコンのメニュー（右クリック）にあります。', '快捷键已关闭。“现在不要”在托盘图标的菜单里（右键）。', 'Сочетание выключено. «Не сейчас» есть в меню значка в трее (правый клик).', 'El atajo está desactivado. «Ahora no» está en el menú del icono de la bandeja (clic derecho).', 'Das Kürzel ist aus. „Jetzt nicht“ findest du im Menü des Symbols im Infobereich (Rechtsklick).', 'Le raccourci est désactivé. « Pas maintenant » est dans le menu de l’icône de la zone de notification (clic droit).', 'O atalho está desligado. “Agora não” está no menu do ícone da bandeja (clique direito).')
_tr7('settings.snooze_hotkey_taken', '今は別のプログラムが {combo} を使っているため、機能しません。別のショートカットを選ぶか、トレイアイコンのメニューの「今はいい」を使ってください。', '{combo} 现在被另一个程序占用，所以不起作用。换一个快捷键，或者用托盘图标菜单里的“现在不要”。', 'Сейчас {combo} занято другой программой, поэтому не работает. Выбери другое сочетание или используй «Не сейчас» в меню значка в трее.', 'Ahora otro programa tiene {combo}, así que no funciona. Elige otro atajo o usa «Ahora no» en el menú del icono de la bandeja.', '{combo} ist gerade von einem anderen Programm belegt und funktioniert daher nicht. Wähl ein anderes Kürzel oder nutze „Jetzt nicht“ im Menü des Symbols im Infobereich.', 'Un autre programme occupe {combo} en ce moment, donc il ne marche pas. Choisis un autre raccourci ou utilise « Pas maintenant » dans le menu de l’icône de la zone de notification.', 'Outro programa está usando {combo} agora, então ele não funciona. Escolha outro atalho ou use “Agora não” no menu do ícone da bandeja.')
_tr7('settings.snooze_hotkey_none', 'オフ', '关闭', 'Выключено', 'Desactivado', 'Aus', 'Désactivé', 'Desligado')
_tr7('settings.snooze_hotkey_types', '{combo}（「{char}」を入力）', '{combo}（会输入“{char}”）', '{combo} (печатает «{char}»)', '{combo} (escribe «{char}»)', '{combo} (tippt „{char}“)', '{combo} (tape « {char} »)', '{combo} (digita “{char}”)')
_tr7('log.hotkey_layout_swapped', '{combo} だと文字「{char}」が打てなくなるため（AltGr は Ctrl+Alt と同じ）、「今はいい」は {new} にしました。設定 → 全般 で変えられます。', '{combo} 会吞掉你键入的字母“{char}”（AltGr 等同于 Ctrl+Alt），所以“现在不要”改用 {new}。可以在 设置 → 通用 中更改。', '{combo} отнимало бы у тебя букву «{char}» (AltGr — это то же, что Ctrl+Alt), поэтому «Не сейчас» теперь на {new}. Изменить это можно в «Настройки → Общие».', '{combo} te quitaría la letra «{char}» al escribir (AltGr es lo mismo que Ctrl+Alt), así que «Ahora no» está en {new}. Puedes cambiarlo en Ajustes → General.', '{combo} würde dir beim Tippen den Buchstaben „{char}“ wegnehmen (AltGr ist dasselbe wie Strg+Alt), daher liegt „Jetzt nicht“ auf {new}. Ändern kannst du das unter Einstellungen → Allgemein.', '{combo} te prendrait la lettre « {char} » quand tu écris (AltGr équivaut à Ctrl+Alt), donc « Pas maintenant » est sur {new}. Tu peux le changer dans Paramètres → Général.', '{combo} tiraria a letra “{char}” da sua digitação (AltGr é o mesmo que Ctrl+Alt), então o “Agora não” ficou em {new}. Você pode mudar isso em Configurações → Geral.')
_tr7('log.hotkey_layout_off', '{combo} だと文字「{char}」が打てなくなるため（AltGr は Ctrl+Alt と同じ）、ショートカットはオンにしません。「今はいい」はトレイアイコンのメニューにあります。', '{combo} 会吞掉你键入的字母“{char}”（AltGr 等同于 Ctrl+Alt），所以我不开启这个快捷键。“现在不要”在托盘图标的菜单里。', '{combo} отнимало бы у тебя букву «{char}» (AltGr — это то же, что Ctrl+Alt), поэтому сочетание я не включаю. «Не сейчас» есть в меню значка в трее.', '{combo} te quitaría la letra «{char}» al escribir (AltGr es lo mismo que Ctrl+Alt), así que dejo el atajo desactivado. «Ahora no» está en el menú del icono de la bandeja.', '{combo} würde dir beim Tippen den Buchstaben „{char}“ wegnehmen (AltGr ist dasselbe wie Strg+Alt), daher schalte ich das Kürzel nicht ein. „Jetzt nicht“ findest du im Menü des Symbols im Infobereich.', '{combo} te prendrait la lettre « {char} » quand tu écris (AltGr équivaut à Ctrl+Alt), donc je n’active pas le raccourci. « Pas maintenant » est dans le menu de l’icône de la zone de notification.', '{combo} tiraria a letra “{char}” da sua digitação (AltGr é o mesmo que Ctrl+Alt), então deixo o atalho desligado. “Agora não” está no menu do ícone da bandeja.')
_tr7('log.hotkey_off', '「今はいい」のショートカットはオフです。トレイアイコンのメニューから静かにさせられます。', '“现在不要”快捷键已关闭。仍可以在托盘图标的菜单里让我安静。', 'Сочетание «Не сейчас» выключено. Заставить меня замолчать можно в меню значка в трее.', 'El atajo de «Ahora no» está desactivado. Puedes silenciarme desde el menú del icono de la bandeja.', 'Das Kürzel für „Jetzt nicht“ ist aus. Zum Schweigen bringst du mich über das Menü des Symbols im Infobereich.', 'Le raccourci « Pas maintenant » est désactivé. Tu peux toujours me faire taire depuis le menu de l’icône de la zone de notification.', 'O atalho do “Agora não” está desligado. Você ainda pode me silenciar pelo menu do ícone da bandeja.')
_tr7('kamae.snoozed_sub_tray', '「今はいい」は {until} まで有効です — それまで声はかけませんが、心拍の計測は続けます。トレイアイコンのメニューで早めに解除できます。', '“现在不要”持续到 {until}——在那之前我不会出声，但会继续测量心率。在托盘图标的菜单里可以提前结束。', '«Не сейчас» действует до {until} — до тех пор я не подам голос, но пульс продолжаю измерять. Отменить раньше можно в меню значка в трее.', '«Ahora no» dura hasta las {until} — hasta entonces no aviso, pero sigo midiendo tu pulso. Puedes cancelarlo antes desde el menú del icono de la bandeja.', '„Jetzt nicht“ gilt bis {until} — bis dahin melde ich mich nicht, den Puls messe ich aber weiter. Früher beendest du es im Menü des Symbols im Infobereich.', '« Pas maintenant » vaut jusqu’à {until} — d’ici là, je ne me manifeste pas, mais je continue à mesurer ton pouls. Tu l’annules plus tôt depuis le menu de l’icône de la zone de notification.', 'O “agora não” vale até {until} — até lá não aviso, mas continuo medindo o seu pulso. Para cancelar antes, use o menu do ícone da bandeja.')
_tr7('tour.triggers.snooze', '都合の悪いときに声をかけたら、{combo} を押して — 30 分間静かにして、計測は続けます。', '如果我在不合适的时候出声，按 {combo}——我会安静半小时，心率照常测量。', 'Если я заговорю в неудачный момент, нажми {combo} — полчаса буду молчать, а пульс продолжу измерять.', 'Si aviso en mal momento, pulsa {combo}: me callo media hora y sigo midiendo.', 'Melde ich mich in einem schlechten Moment, drück {combo} — dann schweige ich eine halbe Stunde und messe weiter.', 'Si je me manifeste au mauvais moment, appuie sur {combo} — je me tais une demi-heure et je continue à mesurer.', 'Se eu avisar numa hora ruim, aperte {combo} — fico quieta por meia hora e continuo medindo.')
_tr7('tour.triggers.snooze_tray', '都合の悪いときに声をかけたら、トレイアイコンのメニューで「今はいい」を選んで — 30 分間静かにして、計測は続けます。', '如果我在不合适的时候出声，在托盘图标的菜单里选“现在不要”——我会安静半小时，心率照常测量。', 'Если я заговорю в неудачный момент, выбери «Не сейчас» в меню значка в трее — полчаса буду молчать, а пульс продолжу измерять.', 'Si aviso en mal momento, elige «Ahora no» en el menú del icono de la bandeja: me callo media hora y sigo midiendo.', 'Melde ich mich in einem schlechten Moment, wähl „Jetzt nicht“ im Menü des Symbols im Infobereich — dann schweige ich eine halbe Stunde und messe weiter.', 'Si je me manifeste au mauvais moment, choisis « Pas maintenant » dans le menu de l’icône de la zone de notification — je me tais une demi-heure et je continue à mesurer.', 'Se eu avisar numa hora ruim, escolha “Agora não” no menu do ícone da bandeja — fico quieta por meia hora e continuo medindo.')
_tr7('log.session_split_sleep', 'パソコンがスリープしていたようです（{min} 分）。スリープが始まった所でセッションを閉じ、新しいセッションを始めました。', '电脑似乎睡眠了（{min} 分钟）。我在睡眠开始处结束了这次记录，并开始了新的记录。', 'Похоже, компьютер спал ({min} мин). Я закрыла сессию там, где начался сон, и начала новую.', 'Parece que el PC estuvo suspendido ({min} min). Cerré la sesión donde empezó la suspensión y empecé una nueva.', 'Der PC hat wohl geschlafen ({min} Min.). Ich habe die Sitzung dort beendet, wo der Ruhezustand begann, und eine neue gestartet.', 'Le PC semble s’être mis en veille ({min} min). J’ai clos la séance là où la veille a commencé et j’en ai commencé une nouvelle.', 'Parece que o PC entrou em suspensão ({min} min). Encerrei a sessão onde a suspensão começou e comecei uma nova.')
_tr7('log.session_split_sleep_end', 'パソコンがスリープしていたようです（{min} 分）。スリープが始まった所でセッションを閉じました。', '电脑似乎睡眠了（{min} 分钟）。我在睡眠开始处结束了这次记录。', 'Похоже, компьютер спал ({min} мин). Я закрыла сессию там, где начался сон.', 'Parece que el PC estuvo suspendido ({min} min). Cerré la sesión donde empezó la suspensión.', 'Der PC hat wohl geschlafen ({min} Min.). Ich habe die Sitzung dort beendet, wo der Ruhezustand begann.', 'Le PC semble s’être mis en veille ({min} min). J’ai clos la séance là où la veille a commencé.', 'Parece que o PC entrou em suspensão ({min} min). Encerrei a sessão onde a suspensão começou.')
_tr7('history.delete_session.btn', 'このセッションを削除', '删除这次记录', 'Удалить эту сессию', 'Borrar esta sesión', 'Diese Sitzung löschen', 'Supprimer cette séance', 'Apagar esta sessão')
_tr7('history.delete_session.title', 'セッションを削除しますか？', '删除这次记录？', 'Удалить сессию?', '¿Borrar la sesión?', 'Sitzung löschen?', 'Supprimer la séance ?', 'Apagar a sessão?')
_tr7('history.delete_session.body', '{date} のセッション（{duration}）を測定ウィンドウごと削除します。元には戻せません。そのあと、このセッションを除いて分析をやり直します。', '将删除 {date} 的记录（{duration}）及其测量窗口，且无法撤销。之后我会在不含它的情况下重新计算分析结论。', 'Сессия от {date} ({duration}) будет удалена вместе с её измерительными окнами, и вернуть её нельзя. Потом я пересчитаю наблюдения без неё.', 'Se borrará la sesión del {date} ({duration}) junto con sus ventanas de medición, y no se puede deshacer. Después recalcularé las observaciones sin ella.', 'Die Sitzung vom {date} ({duration}) wird samt ihren Messfenstern gelöscht, und das lässt sich nicht rückgängig machen. Danach berechne ich die Beobachtungen ohne sie neu.', 'La séance du {date} ({duration}) sera supprimée avec ses fenêtres de mesure, et c’est irréversible. Je recalculerai ensuite les observations sans elle.', 'A sessão de {date} ({duration}) será apagada junto com as janelas de medição, e isso não pode ser desfeito. Depois recalculo as observações sem ela.')
_tr7('history.delete_session.failed', 'セッションを削除できませんでした — 履歴を読み書きできませんでした。', '无法删除这次记录——历史无法读取或写入。', 'Не удалось удалить сессию — историю не получилось прочитать или записать.', 'No pude borrar la sesión: no se pudo leer o escribir el historial.', 'Die Sitzung ließ sich nicht löschen — der Verlauf konnte nicht gelesen oder geschrieben werden.', 'Impossible de supprimer la séance — l’historique n’a pas pu être lu ou écrit.', 'Não consegui apagar a sessão — o histórico não pôde ser lido ou gravado.')
_tr7('log.session_deleted', '{date} のセッションを削除しました。', '我删除了 {date} 的记录。', 'Я удалила сессию от {date}.', 'He borrado la sesión del {date}.', 'Ich habe die Sitzung vom {date} gelöscht.', 'J’ai supprimé la séance du {date}.', 'Apaguei a sessão de {date}.')
_tr7('data.delete.export_first', '先にエクスポート…', '先导出…', 'Сначала экспортировать…', 'Exportar primero…', 'Erst exportieren…', 'Exporter d’abord…', 'Exportar primeiro…')
_tr7('data.delete.stop_first', '先に見守りを止めて — 進行中のセッションが削除のあとにまた保存されてしまいます。', '请先停止关注——否则进行中的记录会在删除后再次保存。', 'Сначала останови наблюдение — иначе текущая сессия после удаления снова сохранится.', 'Primero deja de observar: la sesión en curso se volvería a guardar después de borrar.', 'Beende zuerst die Beobachtung — die laufende Sitzung würde sich nach dem Löschen wieder speichern.', 'Arrête d’abord l’observation — la séance en cours se réenregistrerait après la suppression.', 'Pare de observar primeiro — a sessão em andamento seria salva de novo depois de apagar.')
_tr7('data.delete.pending_session', '保存できなかったセッション', '未能保存的记录', 'сессии, которые не удалось сохранить', 'sesiones que no se pudieron guardar', 'Sitzungen, die nicht gespeichert werden konnten', 'séances qui n’ont pas pu être enregistrées', 'sessões que não puderam ser salvas')
_tr7('session.save_failed.title', 'セッションを保存できませんでした', '记录未保存', 'Сессия не сохранилась', 'La sesión no se guardó', 'Die Sitzung wurde nicht gespeichert', 'La séance n’a pas été enregistrée', 'A sessão não foi salva')
_tr7('log.hr_session_save_failed', 'セッションを保存できませんでした（{err}）。別に取っておいたので、遅くとも次回の起動時に履歴へ追加します。', '无法保存这次记录（{err}）。我已把它另存一边，最迟在下次启动时补进历史。', 'Не удалось сохранить сессию ({err}). Я отложила её в сторону и добавлю в историю не позже следующего запуска.', 'No pude guardar la sesión ({err}). La he apartado y la añadiré al historial, como tarde, en el próximo inicio.', 'Die Sitzung ließ sich nicht speichern ({err}). Ich habe sie beiseitegelegt und füge sie spätestens beim nächsten Start dem Verlauf hinzu.', 'Impossible d’enregistrer la séance ({err}). Je l’ai mise de côté et je l’ajouterai à l’historique au plus tard au prochain démarrage.', 'Não consegui salvar a sessão ({err}). Deixei-a separada e vou adicioná-la ao histórico, no máximo, na próxima vez que o app abrir.')
_tr7('log.hr_session_save_failed_lost', 'セッションを保存できず（{err}）、別に取っておくこともできませんでした — ディスクの空き容量と、データフォルダーがロックされていないかを確認してください。', '无法保存这次记录（{err}），也无法另存一边——请检查磁盘是否还有空间、数据文件夹是否被锁定。', 'Не удалось сохранить сессию ({err}) и даже отложить её — проверь, есть ли место на диске и не заблокирована ли папка с данными.', 'No pude guardar la sesión ({err}) ni tampoco apartarla: comprueba que haya espacio en el disco y que la carpeta de datos no esté bloqueada.', 'Die Sitzung ließ sich nicht speichern ({err}) und auch nicht beiseitelegen — prüf, ob auf der Festplatte Platz ist und der Datenordner nicht gesperrt ist.', 'Impossible d’enregistrer la séance ({err}), ni même de la mettre de côté — vérifie qu’il reste de la place sur le disque et que le dossier des données n’est pas verrouillé.', 'Não consegui salvar a sessão ({err}) nem deixá-la separada — confira se há espaço no disco e se a pasta de dados não está bloqueada.')
_tr7('log.hr_session_no_data', 'セッションは保存されませんでした — 届いた心拍の値が 10 個未満でした。保存するのは、1 分以上続き、心拍の値が 10 個以上あるセッションです。', '这次记录没有保存——收到的心率读数不到 10 个。我只保存持续至少一分钟、并且至少有 10 个心率读数的记录。', 'Сессия не сохранилась — пришло меньше 10 значений пульса. Я сохраняю сессии, которые длятся не меньше минуты и содержат не меньше 10 значений пульса.', 'La sesión no se guardó: llegaron menos de 10 lecturas de pulso. Guardo las sesiones que duran al menos un minuto y tienen al menos 10 lecturas.', 'Die Sitzung wurde nicht gespeichert — es kamen weniger als 10 Pulswerte an. Ich speichere Sitzungen, die mindestens eine Minute dauern und mindestens 10 Pulswerte haben.', 'La séance n’a pas été enregistrée — moins de 10 valeurs de pouls sont arrivées. J’enregistre les séances qui durent au moins une minute et comptent au moins 10 valeurs.', 'A sessão não foi salva — chegaram menos de 10 leituras de pulso. Eu salvo as sessões que duram pelo menos um minuto e têm pelo menos 10 leituras.')
_tr7('log.hr_session_pending_saved', '前回保存できなかった {time} のセッションを履歴に追加しました。', '我把上次没能保存的 {time} 的记录补进了历史。', 'Я добавила в историю сессию от {time}, которую в прошлый раз не удалось сохранить.', 'He añadido al historial la sesión del {time}, que la última vez no se pudo guardar.', 'Ich habe die Sitzung vom {time}, die sich letztes Mal nicht speichern ließ, dem Verlauf hinzugefügt.', 'J’ai ajouté à l’historique la séance du {time}, qui n’avait pas pu être enregistrée la dernière fois.', 'Adicionei ao histórico a sessão de {time}, que da última vez não pôde ser salva.')
_tr7('data.open_folder.btn', 'データフォルダーを開く', '打开数据文件夹', 'Открыть папку с данными', 'Abrir la carpeta de datos', 'Datenordner öffnen', 'Ouvrir le dossier des données', 'Abrir a pasta de dados')
_tr7('data.open_folder.failed', 'データフォルダーを開けませんでした。', '无法打开数据文件夹。', 'Не удалось открыть папку с данными.', 'No pude abrir la carpeta de datos.', 'Der Datenordner ließ sich nicht öffnen.', 'Impossible d’ouvrir le dossier des données.', 'Não consegui abrir a pasta de dados.')
_tr7('data.import.limit', '履歴は最大 {max} セッションまでなので、古いものから外れました（{n} 件）。元のセッションはバックアップに、読み込んだものは読み込んだファイルに残っています。', '历史最多保存 {max} 次记录，所以最早的被去掉了（{n} 次）。你原来的在备份里，导入的仍在导入的文件里。', 'История вмещает не больше {max} сессий, поэтому самые старые выпали (количество: {n}). Твои исходные — в резервной копии, импортированные остаются в импортированном файле.', 'El historial guarda como máximo {max} sesiones, así que las más antiguas quedaron fuera (cantidad: {n}). Las tuyas están en la copia de seguridad y las importadas siguen en el archivo importado.', 'Der Verlauf fasst höchstens {max} Sitzungen, daher sind die ältesten weggefallen (Anzahl: {n}). Deine ursprünglichen liegen in der Sicherung, die importierten bleiben in der importierten Datei.', 'L’historique garde au plus {max} séances, donc les plus anciennes sont tombées (nombre : {n}). Les tiennes sont dans la sauvegarde, les importées restent dans le fichier importé.', 'O histórico guarda no máximo {max} sessões, então as mais antigas ficaram de fora (quantidade: {n}). As suas originais estão no backup e as importadas continuam no arquivo importado.')
_tr7('data.import.backup_where', '「データフォルダーを開く」から見つけられます。', '可以通过“打开数据文件夹”找到它们。', 'Найти их можно через «Открыть папку с данными».', 'Las encontrarás con «Abrir la carpeta de datos».', 'Du findest sie über „Datenordner öffnen“.', 'Tu les trouveras via « Ouvrir le dossier des données ».', 'Você as encontra em “Abrir a pasta de dados”.')
_tr7('edge.partial_refused', '! 音声があるのは {ok}/{total} 件の合図だけ — Microsoft の音声サービスが要求を拒否しました。まず下の「音声を更新」を押して。それでもだめなら、この Zanshin は古くなっているかもしれません — 新しい版を公式の GitHub（Releases）から入手してください。それまでは「音声の種類」を Windows に切り替えられます。', '! 只有 {ok}/{total} 条提示有语音——微软的语音服务拒绝了请求。请先点下方的“更新语音”。如果还是不行，可能是这个版本的 Zanshin 太旧了——请从官方 GitHub（Releases）获取新版本；在那之前，可以把“语音来源”切换为 Windows。', '! голос есть только у {ok}/{total} подсказок — голосовой сервис Microsoft отклонил запрос. Сначала нажми ниже «Обновить голос». Если не поможет, эта версия Zanshin, скорее всего, устарела — новую возьми на официальном GitHub (Releases); до тех пор можно переключить «Источник голоса» на Windows.', '! solo {ok}/{total} avisos tienen voz — el servicio de voz de Microsoft rechazó la solicitud. Primero pulsa «Actualizar la voz» aquí debajo. Si no ayuda, esta versión de Zanshin probablemente esté desactualizada: consigue la nueva en el GitHub oficial (Releases); mientras tanto, puedes cambiar «Origen de la voz» a Windows.', '! nur {ok}/{total} Hinweise haben eine Stimme — der Sprachdienst von Microsoft hat die Anfrage abgelehnt. Klick zuerst unten auf „Stimme aktualisieren“. Hilft das nicht, ist diese Zanshin-Version wohl veraltet — die neue gibt es auf dem offiziellen GitHub (Releases); bis dahin kannst du die Stimmquelle auf Windows umstellen.', '! seulement {ok}/{total} rappels ont leur voix — le service vocal de Microsoft a refusé la demande. Clique d’abord sur « Mettre à jour la voix » ci-dessous. Si ça ne suffit pas, cette version de Zanshin est sans doute dépassée — prends la nouvelle sur le GitHub officiel (Releases) ; d’ici là, tu peux passer la source de la voix sur Windows.', '! só {ok}/{total} avisos têm voz — o serviço de voz da Microsoft recusou o pedido. Primeiro clique em “Atualizar a voz” aqui embaixo. Se não resolver, esta versão do Zanshin provavelmente está desatualizada — pegue a nova no GitHub oficial (Releases); até lá, você pode mudar a fonte da voz para Windows.')
_tr7('edge.partial_other', '! 音声があるのは {ok}/{total} 件の合図だけ — 準備に失敗しました。もう一度試して。', '! 只有 {ok}/{total} 条提示有语音——准备失败了。请重试。', '! голос есть только у {ok}/{total} подсказок — подготовка не удалась. Попробуй ещё раз.', '! solo {ok}/{total} avisos tienen voz — la preparación falló. Vuelve a intentarlo.', '! nur {ok}/{total} Hinweise haben eine Stimme — die Vorbereitung ist fehlgeschlagen. Versuch es noch einmal.', '! seulement {ok}/{total} rappels ont leur voix — la préparation a échoué. Réessaie.', '! só {ok}/{total} avisos têm voz — a preparação falhou. Tente de novo.')
_tr7('log.edge_failed_offline', 'すべての合図に自然な音声を準備できませんでした — 今は Microsoft のサービスにつながりません（インターネットか DNS）。残りは Windows の音声が話します。見守っていないときに、{page} ページの「{retry}」を押すか、Ctrl+K →「{cmd}」を選んでください。', '没能为所有提示准备自然语音——现在连不上微软的服务（网络或 DNS）。其余的由 Windows 语音来说。在我没有关注时，点 {page} 页面上的“{retry}”，或用 Ctrl+K →“{cmd}”。', 'Естественный голос удалось подготовить не для всех подсказок — сервис Microsoft сейчас недоступен (интернет или DNS). Остальное скажет голос Windows. Пока я не наблюдаю, нажми «{retry}» на странице {page} или выбери Ctrl+K → «{cmd}».', 'No pude preparar la voz natural para todos los avisos: ahora no se llega al servicio de Microsoft (internet o DNS). El resto lo dice la voz de Windows. Mientras no observo, pulsa «{retry}» en la página {page} o usa Ctrl+K → «{cmd}».', 'Die natürliche Stimme ließ sich nicht für alle Hinweise vorbereiten — der Dienst von Microsoft ist gerade nicht erreichbar (Internet oder DNS). Den Rest spricht die Windows-Stimme. Solange ich nicht beobachte, klick auf „{retry}“ auf der Seite {page} oder nutze Strg+K → „{cmd}“.', 'Je n’ai pas pu préparer la voix naturelle pour tous les rappels — le service de Microsoft est injoignable pour l’instant (internet ou DNS). La voix de Windows dit le reste. Quand je n’observe pas, clique sur « {retry} » sur la page {page} ou passe par Ctrl+K → « {cmd} ».', 'Não consegui preparar a voz natural para todos os avisos — o serviço da Microsoft está inacessível agora (internet ou DNS). O resto fica com a voz do Windows. Enquanto eu não estiver observando, clique em “{retry}” na página {page} ou use Ctrl+K → “{cmd}”.')
_tr7('log.edge_failed_refused', 'すべての合図に自然な音声を準備できませんでした — Microsoft の音声サービスが要求を拒否しました。見守っていないときに、まず {page} ページの「音声を更新」を押してください。それでもだめなら、この Zanshin は古くなっているかもしれません — 新しい版を公式の GitHub（Releases）から入手してください。それまでは残りを Windows の音声が話します（「音声の種類」を Windows に切り替えることもできます）。やり直すには、そこで「{retry}」を押すか、Ctrl+K →「{cmd}」を選んでください。', '没能为所有提示准备自然语音——微软的语音服务拒绝了请求。在我没有关注时，请先点 {page} 页面上的“更新语音”。如果还是不行，可能是这个版本的 Zanshin 太旧了——请从官方 GitHub（Releases）获取新版本；在那之前，其余的由 Windows 语音来说，也可以把“语音来源”切换为 Windows。想再试一次，就点那里的“{retry}”，或用 Ctrl+K →“{cmd}”。', 'Естественный голос удалось подготовить не для всех подсказок — голосовой сервис Microsoft отклонил запрос. Пока я не наблюдаю, сначала нажми «Обновить голос» на странице {page}. Если не поможет, эта версия Zanshin, скорее всего, устарела — новую возьми на официальном GitHub (Releases); до тех пор остальное скажет голос Windows, или переключи «Источник голоса» на Windows. Чтобы попробовать снова, нажми там «{retry}» или выбери Ctrl+K → «{cmd}».', 'No pude preparar la voz natural para todos los avisos: el servicio de voz de Microsoft rechazó la solicitud. Mientras no observo, pulsa primero «Actualizar la voz» en la página {page}. Si no ayuda, esta versión de Zanshin probablemente esté desactualizada: consigue la nueva en el GitHub oficial (Releases); hasta entonces, el resto lo dice la voz de Windows, o cambia «Origen de la voz» a Windows. Para volver a intentarlo, pulsa allí «{retry}» o usa Ctrl+K → «{cmd}».', 'Die natürliche Stimme ließ sich nicht für alle Hinweise vorbereiten — der Sprachdienst von Microsoft hat die Anfrage abgelehnt. Solange ich nicht beobachte, klick zuerst auf „Stimme aktualisieren“ auf der Seite {page}. Hilft das nicht, ist diese Zanshin-Version wohl veraltet — die neue gibt es auf dem offiziellen GitHub (Releases); bis dahin spricht die Windows-Stimme den Rest, oder stell die Stimmquelle auf Windows um. Für einen neuen Versuch klick dort auf „{retry}“ oder nutze Strg+K → „{cmd}“.', 'Je n’ai pas pu préparer la voix naturelle pour tous les rappels — le service vocal de Microsoft a refusé la demande. Quand je n’observe pas, clique d’abord sur « Mettre à jour la voix » sur la page {page}. Si ça ne suffit pas, cette version de Zanshin est sans doute dépassée — prends la nouvelle sur le GitHub officiel (Releases) ; d’ici là, la voix de Windows dit le reste, ou passe la source de la voix sur Windows. Pour recommencer, clique là-bas sur « {retry} » ou passe par Ctrl+K → « {cmd} ».', 'Não consegui preparar a voz natural para todos os avisos — o serviço de voz da Microsoft recusou o pedido. Enquanto eu não estiver observando, clique primeiro em “Atualizar a voz” na página {page}. Se não resolver, esta versão do Zanshin provavelmente está desatualizada — pegue a nova no GitHub oficial (Releases); até lá, o resto fica com a voz do Windows, ou mude a fonte da voz para Windows. Para tentar de novo, clique lá em “{retry}” ou use Ctrl+K → “{cmd}”.')
_tr7('log.edge_failed_other', 'すべての合図に自然な音声を準備できませんでした（{err}）。残りは Windows の音声が話します。見守っていないときに、{page} ページの「{retry}」を押すか、Ctrl+K →「{cmd}」を選んでください。', '没能为所有提示准备自然语音（{err}）。其余的由 Windows 语音来说。在我没有关注时，点 {page} 页面上的“{retry}”，或用 Ctrl+K →“{cmd}”。', 'Естественный голос удалось подготовить не для всех подсказок ({err}). Остальное скажет голос Windows. Пока я не наблюдаю, нажми «{retry}» на странице {page} или выбери Ctrl+K → «{cmd}».', 'No pude preparar la voz natural para todos los avisos ({err}). El resto lo dice la voz de Windows. Mientras no observo, pulsa «{retry}» en la página {page} o usa Ctrl+K → «{cmd}».', 'Die natürliche Stimme ließ sich nicht für alle Hinweise vorbereiten ({err}). Den Rest spricht die Windows-Stimme. Solange ich nicht beobachte, klick auf „{retry}“ auf der Seite {page} oder nutze Strg+K → „{cmd}“.', 'Je n’ai pas pu préparer la voix naturelle pour tous les rappels ({err}). La voix de Windows dit le reste. Quand je n’observe pas, clique sur « {retry} » sur la page {page} ou passe par Ctrl+K → « {cmd} ».', 'Não consegui preparar a voz natural para todos os avisos ({err}). O resto fica com a voz do Windows. Enquanto eu não estiver observando, clique em “{retry}” na página {page} ou use Ctrl+K → “{cmd}”.')
_tr7('log.world_switch_session', '進行中のセッションは「{world}」のままです — 「{new}」は次に見守りを始めたときから有効になります。', '进行中的记录仍留在“{world}”——“{new}”从下次开始关注时生效。', 'Текущая сессия остаётся в мире «{world}» — «{new}» действует со следующего запуска наблюдения.', 'La sesión en curso sigue en {world}: {new} vale desde la próxima vez que inicies la observación.', 'Die laufende Sitzung bleibt in der Welt „{world}“ — „{new}“ gilt ab dem nächsten Start der Beobachtung.', 'La séance en cours reste dans le monde « {world} » — « {new} » vaut dès le prochain lancement de l’observation.', 'A sessão em andamento continua em {world} — {new} vale a partir da próxima vez que você iniciar a observação.')
_tr7('hr.ip_virtual', '（VPN/仮想）', '（VPN/虚拟）', '(VPN/виртуальный)', '(VPN/virtual)', '(VPN/virtuell)', '(VPN/virtuelle)', '(VPN/virtual)')
_tr7('hr.ip_virtual_note', 'このアドレスは VPN か仮想アダプターのものです — 電話からはたいてい届きません。VPN を使っていますか？ オフにするか、VPN でローカルネットワークへのアクセスを許可してください。', '这个地址属于 VPN 或虚拟网卡——手机通常连不上它。开着 VPN 吗？把它关掉，或在其中允许访问局域网。', 'Этот адрес принадлежит VPN или виртуальному адаптеру — телефон обычно до него не дотянется. Включён VPN? Выключи его или разреши в нём доступ к локальной сети.', 'Esta dirección es de una VPN o de un adaptador virtual: el móvil normalmente no llega a ella. ¿Usas una VPN? Desactívala o permite en ella el acceso a la red local.', 'Diese Adresse gehört zu einem VPN oder virtuellen Adapter — das Handy erreicht sie meist nicht. VPN an? Schalt es aus oder erlaube darin den Zugriff aufs lokale Netzwerk.', 'Cette adresse appartient à un VPN ou à un adaptateur virtuel — le téléphone ne peut généralement pas l’atteindre. Un VPN est actif ? Coupe-le ou autorise-y l’accès au réseau local.', 'Este endereço é de uma VPN ou de um adaptador virtual — o celular geralmente não consegue alcançá-lo. Usando VPN? Desligue-a ou permita nela o acesso à rede local.')
_tr7('settings.hr_ip_virtual_note', 'この欄のアドレスは VPN か仮想アダプターのものです — 電話からはたいてい届きません。0.0.0.0 のままにしておくのがおすすめです。', '此栏中的地址属于 VPN 或虚拟网卡——手机通常连不上它。最好保留 0.0.0.0。', 'Адрес в этом поле принадлежит VPN или виртуальному адаптеру — телефон обычно до него не дотянется. Лучше оставь 0.0.0.0.', 'La dirección de este campo es de una VPN o de un adaptador virtual: el móvil normalmente no llega a ella. Mejor deja 0.0.0.0.', 'Die Adresse in diesem Feld gehört zu einem VPN oder virtuellen Adapter — das Handy erreicht sie meist nicht. Lass lieber 0.0.0.0 stehen.', 'L’adresse de ce champ appartient à un VPN ou à un adaptateur virtuel — le téléphone ne peut généralement pas l’atteindre. Mieux vaut laisser 0.0.0.0.', 'O endereço deste campo é de uma VPN ou de um adaptador virtual — o celular geralmente não consegue alcançá-lo. Melhor deixar 0.0.0.0.')
_tr7('log.quit_questionnaire_saved', '終了するときに、アンケートに記入済みの回答を保存しました。', '退出时，我保存了问卷里已经填写的回答。', 'При выходе я сохранила ответы, уже отмеченные в опросе.', 'Al salir, guardé las respuestas que ya estaban en el cuestionario.', 'Beim Beenden habe ich die bereits ausgefüllten Antworten des Fragebogens gespeichert.', 'En quittant, j’ai enregistré les réponses déjà remplies dans le questionnaire.', 'Ao sair, salvei as respostas já preenchidas no questionário.')
_tr7('log.quit_questionnaire_skipped', '終了するときに、未記入のアンケートを閉じました — セッションは回答なしで保存されています。', '退出时，我关闭了空白的问卷——记录已保存，只是没有回答。', 'При выходе я закрыла пустой опрос — сессия сохранена без ответов.', 'Al salir, cerré el cuestionario vacío: la sesión queda guardada sin respuestas.', 'Beim Beenden habe ich den leeren Fragebogen geschlossen — die Sitzung bleibt ohne Antworten gespeichert.', 'En quittant, j’ai fermé le questionnaire vide — la séance reste enregistrée sans réponses.', 'Ao sair, fechei o questionário vazio — a sessão continua salva sem respostas.')

# --- 0.3 batch 4: dictionary and copy of existing keys (onboarding step 1) ---
# Until now the introduction never asked what the player needs for the
# first heart rate reading. The sentence is true to what the app knows: a
# smartwatch with a companion app on the phone that sends heart rate
# straight to this PC (OSC, UDP, obs-websocket - README "Getting your
# heart rate in"), and the phone and PC on one home network. A chest
# strap was here until batch 4b - nobody verified the path with it and
# the README talks about watches.
STRINGS.update({
    'ob.step1.need': _sk_en(
        'Čo budeš potrebovať: chytré hodinky, ktoré merajú tep, k nim appku v telefóne, ktorá tep pošle do tohto počítača, a telefón aj počítač v tej istej domácej sieti (Wi‑Fi).',
        'What you’ll need: a smartwatch that measures heart rate, its companion phone app that sends the heart rate to this PC, and the phone and the PC on the same home network (Wi‑Fi).'),
})
_tr7('ob.step1.need', '必要なもの：心拍を測るスマートウォッチ、その心拍をこのPCに送る電話のコンパニオンアプリ、そして同じ家庭内ネットワーク（Wi‑Fi）につながった電話とPC。', '你需要：一块能测心率的智能手表、一个把心率发送到这台电脑的配套手机应用，以及连在同一个家庭网络（Wi‑Fi）上的手机和电脑。', 'Что понадобится: умные часы, которые измеряют пульс, приложение-компаньон на телефоне, которое отправит пульс на этот компьютер, и телефон с компьютером в одной домашней сети (Wi‑Fi).', 'Qué necesitas: un reloj inteligente que mida el pulso, su app complementaria en el móvil que envíe el pulso a este PC, y el móvil y el PC en la misma red de casa (Wi‑Fi).', 'Was du brauchst: eine Smartwatch mit Pulsmessung, die passende App auf dem Handy, die den Puls an diesen PC schickt, und Handy und PC im selben Heimnetz (WLAN).', 'Ce qu’il te faut : une montre connectée qui mesure le pouls, son app compagnon sur le téléphone qui envoie le pouls à ce PC, et le téléphone et le PC sur le même réseau domestique (Wi‑Fi).', 'Do que você precisa: um smartwatch que meça o pulso, o app complementar no celular que envie o pulso para este PC, e o celular e o PC na mesma rede de casa (Wi‑Fi).')

# --- 0.3 batch 4b: VPN/hotspot and the post-session questionnaire in Work ---
# The Windows mobile hotspot (Wi-Fi Direct) is not a VPN: a phone
# connected to the hotspot can reach its address - a neutral label, no
# warning (`netinfo.druh_adaptera`). The session trace in the
# questionnaire in the Work world does not say "you played"
# (`SessionEndDialog`, like `session.end.title_work`).
STRINGS.update({
    'hr.ip_hotspot': _sk_en('(hotspot)', '(hotspot)'),
    'session.end.trace_hint_work': _sk_en(
        'Tep počas celej relácie. Trojuholníky sú pripomienky; tenký pruh ukazuje, kedy sa pravdepodobne pracovalo (klávesnica, myš alebo ovládač).',
        'Your heart rate across the whole session. Triangles are cues; the thin band shows when you were probably working (keyboard, mouse or controller).'),
})
_tr7('hr.ip_hotspot', '（ホットスポット）', '（热点）', '(хот-спот)', '(punto de acceso)', '(Hotspot)', '(point d’accès)', '(hotspot)')
_tr7('session.end.trace_hint_work', 'セッション全体の心拍。三角は合図、細い帯はおそらく作業していた時間（キーボード、マウス、コントローラー）を示します。', '整个记录期间的心率。三角形是提示；细条显示你大概在工作的时间（键盘、鼠标或手柄）。', 'Пульс за всю сессию. Треугольники — подсказки; тонкая полоса показывает, когда, вероятно, шла работа (клавиатура, мышь или контроллер).', 'Tu pulso durante toda la sesión. Los triángulos son avisos; la franja fina muestra cuándo probablemente estabas trabajando (teclado, ratón o mando).', 'Dein Puls über die ganze Sitzung. Die Dreiecke sind Hinweise; der schmale Streifen zeigt, wann vermutlich gearbeitet wurde (Tastatur, Maus oder Controller).', 'Ton pouls sur toute la séance. Les triangles sont les rappels ; la fine bande montre quand tu travaillais probablement (clavier, souris ou manette).', 'O seu pulso durante toda a sessão. Os triângulos são avisos; a faixa fina mostra quando você provavelmente estava trabalhando (teclado, mouse ou controle).')

_DOPLNENE_PREKLADY = {
    "kamae.no_hr": {"ja": "心拍を待っています", "zh": "正在等待心率", "ru": "Ожидаю пульс", "es": "Esperando las pulsaciones", "de": "Warte auf den Puls", "fr": "En attente du rythme cardiaque", "pt": "Aguardando o pulso"},
    "settings.hr_status_no_client": {
        'ja': '受信オン — 電話はまだ接続していません',
        'zh': '接收已开启——手机还没有连接',
        'ru': 'Приём включён — телефон ещё не подключился',
        'es': 'Recepción activada: el móvil aún no se ha conectado',
        'de': 'Empfang an — das Handy hat sich noch nicht verbunden',
        'fr': 'Réception activée — le téléphone ne s’est pas encore connecté',
        'pt': 'Recepção ligada — o celular ainda não se conectou',
    },
    "settings.hr_status_busy_gave_up": {"ja": "ポートが使用中です — センサーをオフにしました", "zh": "端口被占用——传感器已关闭", "ru": "Порт занят — датчик выключен", "es": "El puerto está ocupado — sensor apagado", "de": "Port ist belegt — Sensor ausgeschaltet", "fr": "Le port est occupé — capteur désactivé", "pt": "A porta está ocupada — sensor desligado"},
    "guide.panel_subtitle": {"ja": "それぞれの合図のときに体の中で何が起きているか、そしてアプリが声をかけてきたら何をすればいいか。", "zh": "每条提示出现时你的身体会发生什么，以及当应用出声提醒时你该怎么做。", "ru": "Что происходит в твоём теле при каждой подсказке и что с этим делать, когда приложение подаёт голос.", "es": "Qué pasa en tu cuerpo con cada aviso y qué hacer cuando la app te habla.", "de": "Was in deinem Körper bei jedem Hinweis passiert und was du damit machen kannst, wenn die App sich meldet.", "fr": "Ce qui se passe dans ton corps à chaque rappel, et quoi faire quand l’app te parle.", "pt": "O que acontece no seu corpo a cada aviso e o que fazer quando o app avisa."},
    "about.title": {"ja": "このアプリについて", "zh": "关于", "ru": "О приложении", "es": "Acerca de", "de": "Über die App", "fr": "À propos", "pt": "Sobre"},
    "about.lead": {
        'ja': 'みなさん、こんにちは。Dandurfinです。',
        'zh': '大家好，我是 Dandurfin。',
        'ru': 'Всем привет, это Dandurfin.',
        'es': 'Hola a todos, aquí Dandurfin.',
        'de': 'Hallo zusammen, hier ist Dandurfin.',
        'fr': 'Salut à tous, ici Dandurfin.',
        'pt': 'Olá, pessoal, aqui é o Dandurfin.',
    },
    "about.body": {
        'ja': 'そもそもZanshinはなぜ生まれたのか。一日の大半をパソコンの前で過ごし、配信をしたりゲームをしたりしている僕は、時間が経つうちにあるパターンに気づきました。ゲームをしていると、僕たちはよく完全な「オートパイロット」状態にすべり込んでしまいます。夢中になりすぎて時間も自分の体のことも見失ってしまうか、逆に、うまくいかないと無駄にティルトして苛立ってしまうか、どちらかなんです。\n\n僕は、激しいアクションの最中でも、ピリピリしたランクマッチの中でも、冷静な頭を保って「フロー」の状態でいられる方法を探していました。そんなときに出会ったのが、残心（ざんしん）という考え方です。武道では、完全に集中しながらもリラックスし、何にでも対応できる澄んだ心の状態を指す言葉です。\n\nこのアプリは、ただの個人的な必要から書きました。燃え尽きないように支えてくれて、ときどき深呼吸をするよう思い出させてくれて、地に足をつけさせてくれる——そんな、そっと背後で働いてくれる相棒がほしかったんです。複雑で難解な修行の話ではありません。ただ、ゲームをもっと楽しんで、もっとうまくプレイして、そして何より、何でもないことでティルトしない。それだけのことです。\n\n僕も同じ世代の多くの人と同じように、ゲームと一緒に育ちました。目の奥では、外から見えるよりずっと多くのことが起きています。Zanshinは、それを平和なやり方で試してみようという僕なりの試みです。気づいてくれて、何も求めず、何も売らないもの。\n\nそして正直に言うと、僕はプログラマーでもアーティストでもありません。このアプリは「バイブコーディング」で書きました——つまりAIと一緒に、一文ずつ、走りながら覚えていったんです。僕が持ち込んだのは、アイデアと、パソコンの前で過ごした長い年月だけです。\n\n僕は巨人の肩の上に立っています。このアプリがやっていることで、僕が考え出したものは何ひとつありません——呼吸も、集中も、ゆるめた顎も、心拍とストレスの研究も、これを書くのに使った道具も。すべて誰かが僕より先に作り、そして誰でも使えるように開いたまま残しておいてくれたものです。だからこそZanshinは、GPLv3ライセンスのもとで無料かつオープンです。誰でもコードを読み、書き換え、次へ渡すことができます——ただ、閉じてしまうことだけはできません。次へ渡す人は、ソースコードと同じライセンスも一緒に手渡さなければなりません。僕はこうして受け継ぎ、こうして同じように渡していきたいのです。\n\nこの考え方にピンとくる人も、ただゲームをして一緒にゆるく過ごしたいだけの人も、ぜひ僕たちのコミュニティに立ち寄ってください：',
        'zh': 'Zanshin 到底是怎么诞生的？作为一个每天有很大一部分时间都泡在电脑前、直播和打游戏的人，我慢慢发现了一个规律。玩游戏时，我们常常会完全进入“自动驾驶”模式。要么是太投入，以至于彻底忘了时间，也忘了自己的身体；要么反过来，一不顺就上头，为不该生气的事情生气。\n\n我一直在找一种方法，让自己即便身处激烈的战斗或紧张的排位赛中，也能保持冷静的头脑，留在“心流”里。也正是在那时，我接触到了 zanshin 这个概念——在武术里，它指的是一种全神贯注、放松、头脑清明、随时准备应对一切的状态。\n\n写这个应用，纯粹是出于我自己一个很简单的需求。我想要一个不起眼、在后台默默帮忙的小助手，让我不至于把自己耗空，时不时提醒我深呼吸一下，把我拉回地面。这里没有什么复杂玄乎的练习，说到底就是为了让我们玩游戏更开心、发挥得更好，最重要的是——别为了鸡毛蒜皮的事上头。\n\n我和同龄的很多人一样，是玩着游戏长大的。眼睛背后发生的事，比别人看到的多得多。Zanshin 是我的一次尝试，想用和平的方式去面对：一个会注意到你、什么都不要、什么都不卖的东西。\n\n再说得直白点：我既不是程序员，也不是美术。这个应用是我用 vibe coding 的方式写出来的——和 AI 一起，一行一行地敲，边做边学。我带进来的，就是这个点子，还有多年泡在电脑前的经历。\n\n我是站在巨人的肩膀上。这个应用所做的一切，没有一样是我发明的——呼吸、专注、放松的下颌、关于心率和压力的研究，还有写它所用的那些工具。这一切都是别人在我之前做好、并且免费公开出来的。正因如此，Zanshin 在 GPLv3 许可证下免费且开放：任何人都可以阅读代码、修改它、把它传下去——唯独不能把它封闭起来。谁把它传下去，就必须连同源代码和同一份许可证一起交出去。我是这样继承来的，也想这样传下去。\n\n如果你认同这样的心态，或者只是想一起打打游戏、聊聊天，一定要来我们的社区坐坐：',
        'ru': 'Почему вообще появился Zanshin? Как человек, который проводит за компьютером огромную часть дня — стримлю и играю, — я со временем заметил закономерность. Играя, мы часто скатываемся в полный «автопилот». Либо увлекаемся так, что теряем счёт времени и забываем о собственном теле, либо, наоборот, ловим ненужный тильт и злимся, когда что-то не выходит.\n\nЯ искал способ сохранять холодную голову и оставаться в «потоке» даже посреди жаркого экшена или в потных ранкед-матчах. Тогда я и наткнулся на понятие zanshin — в боевых искусствах оно означает состояние полной сосредоточенности, расслабленности и ясной головы, готовой ко всему.\n\nЭто приложение я написал из простой личной потребности. Мне хотелось незаметного помощника на фоне, который не даст мне выгореть, время от времени напомнит глубоко вдохнуть и удержит меня на земле. Речь не о каких-то сложных эзотерических упражнениях — просто о том, чтобы игры приносили больше удовольствия, чтобы играть лучше и, главное, чтобы не злиться из-за ерунды.\n\nЯ вырос с играми, как многие из моего поколения. За глазами происходит больше, чем кто-либо видит. Zanshin — моя попытка попробовать по-мирному: что-то, что замечает, ничего не требует и ничего не продаёт.\n\nИ честно: я не программист и не художник. Это приложение я написал вайб-кодингом — то есть вместе с ИИ, строчка за строчкой, учась по ходу дела. То, что привнёс я, — это идея и годы, проведённые за компьютером.\n\nЯ стою на плечах гигантов. Ничего из того, что делает это приложение, я не придумал — дыхание, сосредоточенность, расслабленная челюсть, исследования о пульсе и стрессе, да и инструменты, на которых всё это написано. Всё это кто-то сделал до меня и оставил в свободном доступе. Поэтому Zanshin бесплатный и открытый под лицензией GPLv3: любой может посмотреть код, изменить его и передать дальше — только закрыть его нельзя. Кто передаёт его дальше, должен отдать вместе с ним и исходный код, и ту же самую лицензию. Я получил это так и хочу так же передать дальше.\n\nЕсли тебе близок этот настрой или ты просто хочешь поиграть и потусить, обязательно загляни к нам:',
        'es': '¿Por qué surgió Zanshin en realidad? Como alguien que pasa gran parte del día delante del PC —haciendo streaming y jugando— con el tiempo me di cuenta de un patrón. Al jugar caemos a menudo en el «piloto automático» total. O nos metemos tanto que perdemos la noción del tiempo y de nuestro propio cuerpo, o al revés, pillamos un tilt innecesario y nos frustramos cuando las cosas no salen.\n\nBuscaba una forma de mantener la cabeza fría y quedarme en el «flow» incluso en plena acción o en partidas sweaty de ranked. Fue entonces cuando di con el concepto de zanshin — que en las artes marciales designa un estado de concentración plena, relajación y mente clara, lista para cualquier cosa.\n\nProgramé esta app por una simple necesidad personal. Quería un ayudante discreto en segundo plano que no me deje quemarme, que de vez en cuando me recuerde respirar hondo y que me mantenga con los pies en la tierra. No se trata de ningún ejercicio esotérico complicado; se trata simplemente de disfrutar más de los juegos, jugar mejor y, sobre todo, no cabrearnos por nada.\n\nCrecí con los videojuegos, como mucha gente de mi generación. Detrás de los ojos pasa más de lo que nadie ve. Zanshin es mi intento de probarlo en paz: algo que se da cuenta, no pide nada y no vende nada.\n\nY os lo digo sin rodeos: no soy programador ni artista. Esta app la hice a base de vibe coding — junto con la IA, línea a línea, aprendiendo sobre la marcha. Lo que puse yo es la idea y los años pasados delante del PC.\n\nEstoy a hombros de gigantes. Nada de lo que hace esta app lo inventé yo — la respiración, la concentración, la mandíbula relajada, la investigación sobre el ritmo cardíaco y el estrés, las herramientas con las que está escrita. Todo eso ya lo hizo alguien antes que yo y lo dejó a disposición de todos. Por eso Zanshin es gratuito y abierto bajo la licencia GPLv3: cualquiera puede leer el código, modificarlo y pasarlo adelante — lo único que no puede es cerrarlo. Quien lo pase adelante tiene que entregar también el código fuente y la misma licencia. Yo lo heredé así y quiero entregarlo de la misma manera.\n\nSi esta forma de ver las cosas te encaja, o si solo quieres echar unas partidas y pasar el rato, pásate sin falta por nuestra comunidad:',
        'de': 'Warum ist Zanshin eigentlich entstanden? Als jemand, der einen großen Teil des Tages am PC verbringt — ich streame und zocke — ist mir mit der Zeit ein Muster aufgefallen. Beim Spielen rutschen wir oft in den kompletten „Autopilot“. Entweder vertiefen wir uns so sehr, dass wir das Zeitgefühl und den eigenen Körper völlig verlieren, oder wir fangen uns umgekehrt unnötigen Tilt ein und ärgern uns, wenn es nicht läuft.\n\nIch habe nach einem Weg gesucht, einen kühlen Kopf zu bewahren und selbst mitten in der Action oder in sweaty Ranked-Matches im „Flow“ zu bleiben. Damals bin ich auf den Begriff Zanshin gestoßen — in den Kampfkünsten bezeichnet er einen Zustand voller Konzentration, Entspannung und eines klaren Kopfes, der auf alles vorbereitet ist.\n\nDiese App habe ich aus einem ganz einfachen persönlichen Bedürfnis geschrieben. Ich wollte einen unaufdringlichen Helfer im Hintergrund, der mich nicht ausbrennen lässt, mich ab und zu ans tiefe Durchatmen erinnert und mich auf dem Boden hält. Es geht um keine komplizierten esoterischen Übungen — es geht einfach darum, dass uns die Spiele mehr Spaß machen, dass wir besser spielen und vor allem, dass wir uns nicht wegen Kleinigkeiten aufregen.\n\nIch bin mit Games aufgewachsen, wie viele aus meiner Generation. Hinter den Augen passiert mehr, als irgendwer sieht. Zanshin ist mein Versuch, es im Frieden zu probieren: etwas, das hinschaut, nichts will und nichts verkauft.\n\nUnd ganz ehrlich: Ich bin weder Programmierer noch Grafiker. Diese App habe ich per Vibe Coding geschrieben — also zusammen mit KI, Satz für Satz, und ich habe im Laufen dazugelernt. Was ich beigetragen habe, ist die Idee und die Jahre, die ich am PC verbracht habe.\n\nIch stehe auf den Schultern von Riesen. Nichts von dem, was die App tut, habe ich erfunden — das Atmen, die Konzentration, der gelöste Kiefer, die Forschung zu Puls und Stress und auch die Werkzeuge, in denen das Ganze geschrieben ist. Das alles hat jemand vor mir gemacht und frei zugänglich gelassen. Deshalb ist Zanshin kostenlos und offen unter der GPLv3-Lizenz: Jeder kann sich den Code ansehen, ihn ändern und weitergeben — nur zumachen darf er ihn nicht. Wer ihn weitergibt, muss den Quellcode und dieselbe Lizenz mitliefern. Ich habe es so geerbt und ich will es genauso weitergeben.\n\nWenn dir diese Einstellung zusagt, oder wenn du einfach zocken und quatschen willst, schau unbedingt bei uns vorbei:',
        'fr': "Pourquoi Zanshin a-t-il vu le jour, au juste ? En tant que personne qui passe une grande partie de sa journée devant le PC — à streamer et à jouer — j'ai fini par remarquer un schéma qui revient. En jouant, on bascule souvent en mode « pilote automatique » total. Soit on est tellement absorbé qu'on perd complètement la notion du temps et de son propre corps, soit, à l'inverse, on attrape un tilt inutile et on s'agace dès que ça ne va pas.\n\nJe cherchais un moyen de garder la tête froide et de rester dans le « flow » même en pleine action ou dans des parties classées bien sweaty. C'est là que je suis tombé sur le concept de zanshin — qui, dans les arts martiaux, désigne un état de concentration totale, de détente et d'esprit clair, prêt à tout.\n\nJ'ai codé cette appli par simple besoin personnel. Je voulais un assistant discret, en arrière-plan, qui m'empêche de m'épuiser, qui me rappelle de respirer profondément de temps en temps et qui me garde les pieds sur terre. Rien à voir avec des exercices ésotériques compliqués — il s'agit simplement de prendre plus de plaisir à jouer, de mieux jouer et, surtout, de ne pas s'énerver pour un rien.\n\nJ'ai grandi avec les jeux vidéo, comme beaucoup de ma génération. Derrière les yeux, il se passe plus de choses que ce que l'on voit. Zanshin, c'est ma tentative d'essayer en paix : quelque chose qui remarque, ne demande rien et ne vend rien.\n\nEt soyons clairs : je ne suis ni programmeur ni graphiste. J'ai codé cette appli en vibe coding — avec l'IA, ligne par ligne, en apprenant au fur et à mesure. Ce que j'y ai apporté, moi, c'est l'idée et les années passées devant le PC.\n\nJe me tiens sur les épaules de géants. Rien de ce que fait cette appli n'a été inventé par moi — la respiration, la concentration, la mâchoire détendue, les recherches sur le rythme cardiaque et le stress, les outils dans lesquels elle est écrite. Quelqu'un a fait tout ça avant moi et l'a laissé en libre accès. C'est pour ça que Zanshin est gratuit et ouvert sous la licence GPLv3 : n'importe qui peut lire le code, le modifier et le transmettre — il ne peut simplement pas le refermer. Celui qui le transmet doit remettre avec lui le code source et cette même licence. J'en ai hérité ainsi, et je veux le transmettre de la même façon.\n\nSi cet état d'esprit te parle, ou si tu veux juste jouer et passer un bon moment, passe faire un tour dans notre communauté :",
        'pt': 'Por que, afinal, o Zanshin surgiu? Como alguém que passa boa parte do dia no PC — fazendo stream e jogando —, com o tempo percebi um padrão. Jogando, muitas vezes entramos no modo “piloto automático” total. Ou ficamos tão absorvidos que perdemos completamente a noção do tempo e do próprio corpo, ou, ao contrário, entramos num tilt desnecessário e ficamos frustrados quando as coisas dão errado.\n\nEu estava procurando um jeito de manter a cabeça fria e ficar no “flow” mesmo no meio da ação intensa ou de partidas sweaty de ranked. Foi aí que dei de cara com o conceito de zanshin — que, nas artes marciais, designa um estado de concentração total, descontração e mente limpa, pronta para tudo.\n\nEscrevi este app por uma simples necessidade pessoal. Eu queria um ajudante discreto em segundo plano que não me deixasse esgotar, que de vez em quando me lembrasse de respirar fundo e que me mantivesse com os pés no chão. Não são exercícios esotéricos complicados — é simplesmente para a gente se divertir mais com os jogos, jogar melhor e, acima de tudo, não entrar em tilt à toa.\n\nCresci com os jogos, como muita gente da minha geração. Por trás dos olhos acontece mais do que se vê. O Zanshin é a minha tentativa de tentar isso em paz: algo que percebe, não quer nada e não vende nada.\n\nE agora sem rodeios: não sou programador nem artista. Fiz este app com vibe coding — ou seja, junto com a IA, linha por linha, aprendendo pelo caminho. O que eu trouxe foi a ideia e os anos passados no PC.\n\nEstou apoiado nos ombros de gigantes. Nada do que este app faz foi inventado por mim — a respiração, a concentração, a mandíbula solta, a pesquisa sobre frequência cardíaca e estresse, e as ferramentas em que ele foi escrito. Alguém fez tudo isso antes de mim e deixou livremente disponível. É por isso que o Zanshin é gratuito e aberto sob a licença GPLv3: qualquer pessoa pode ver o código, alterá-lo e passá-lo adiante — só não pode fechá-lo. Quem o passa adiante tem de entregar junto também o código-fonte e a mesma licença. Eu o herdei assim e assim quero passá-lo adiante.\n\nSe essa atitude tem a ver com você, ou se você só quer jogar um pouco e bater papo, passe com certeza na nossa comunidade:',
    },
    "about.between_lines": {"ja": "行間を読む人へ：\n\nこのアプリはストレスを測らない。測るのは、すきま——心拍が告げるものと、あなたが実際に感じるものとの間の。数字は表面、あなたは深み。\n\nそのすきまを自分の中で聞けるようになれば、ほかの場所でも聞こえてくる——人が書くことと思っていること、求めることと必要としていることの間に。\n\n何も失われない。ただ姿を変えるだけ——注意もまた。手のひらは開いたままで。", "zh": "给读得懂字里行间的人：\n\n这个应用不测量压力。它测量的是那道缝隙——你的心率所说的，与你真正所感受的之间。数字是表面；你是深处。\n\n当你学会在自己心里听见那道缝隙，你也会开始在别处听见它——在人们所写的与所想的、所求的与所需的之间。\n\n没有什么会失去。只是转化——注意力也是。把手掌摊开。", "ru": "Для того, кто читает между строк:\n\nЭто приложение не измеряет стресс. Оно измеряет зазор — между тем, что говорит твой пульс, и тем, что ты на самом деле чувствуешь. Число — это поверхность; ты — глубина.\n\nИ когда ты научишься слышать этот зазор в себе, ты начнёшь слышать его и в другом — в том, что люди пишут и что думают, чего просят и что им нужно.\n\nНичто не теряется. Оно лишь преображается — и внимание тоже. Держи ладонь открытой.", "es": "Para quien lee entre líneas:\n\nEsta app no mide el estrés. Mide la brecha — entre lo que dice tu pulso y lo que de verdad sientes. El número es la superficie; tú eres la profundidad.\n\nY cuando aprendas a oír esa brecha en ti, empezarás a oírla también en otras partes — en lo que la gente escribe y lo que piensa, en lo que pide y lo que necesita.\n\nNada se pierde. Solo se transforma — también la atención. Mantén la palma abierta.", "de": "Für den, der zwischen den Zeilen liest:\n\nDiese App misst nicht den Stress. Sie misst die Lücke — zwischen dem, was dein Puls sagt, und dem, was du wirklich fühlst. Die Zahl ist die Oberfläche; du bist die Tiefe.\n\nUnd wenn du lernst, diese Lücke in dir zu hören, wirst du sie auch anderswo hören — in dem, was Menschen schreiben und was sie meinen, worum sie bitten und was sie brauchen.\n\nNichts geht verloren. Es wandelt sich nur — auch die Aufmerksamkeit. Halte die Handfläche offen.", "fr": "Pour celui qui lit entre les lignes :\n\nCette appli ne mesure pas le stress. Elle mesure l'écart — entre ce que dit ton pouls et ce que tu ressens vraiment. Le chiffre est la surface ; toi, tu es la profondeur.\n\nEt quand tu apprendras à entendre cet écart en toi, tu commenceras à l'entendre ailleurs aussi — dans ce que les gens écrivent et ce qu'ils pensent, ce qu'ils demandent et ce dont ils ont besoin.\n\nRien ne se perd. Cela se transforme seulement — l'attention aussi. Garde la paume ouverte.", "pt": "Para quem lê nas entrelinhas:\n\nEste app não mede o estresse. Mede a lacuna — entre o que o seu pulso diz e o que você realmente sente. O número é a superfície; você é a profundidade.\n\nE quando você aprender a ouvir essa lacuna em si mesmo, vai começar a ouvi-la também em outros lugares — no que as pessoas escrevem e no que pensam, no que pedem e no que precisam.\n\nNada se perde. Apenas se transforma — a atenção também. Mantenha a palma aberta."},
    "log.cue_visual_failed": {
        'ja': 'ゲーム中の画像が描画されませんでした — この合図は計測に含めません。',
        'zh': '游戏中的图片没有画出来——这条提示不计入测量。',
        'ru': 'Картинка в игре не отрисовалась — эта подсказка в измерение не идёт.',
        'es': 'La imagen en el juego no se dibujó: este aviso no cuenta para la medición.',
        'de': 'Das Bild im Spiel wurde nicht gezeichnet — dieser Hinweis zählt nicht zur Messung.',
        'fr': 'L’image en jeu ne s’est pas affichée — ce rappel ne compte pas dans la mesure.',
        'pt': 'A imagem no jogo não foi desenhada — este aviso não conta na medição.',
    },
    "session.context.save_failed": {"ja": "このセッションのコンテキストを保存できませんでした——回答は保存されませんでした。", "zh": "无法保存这次会话的情境——你的回答没有被保存下来。", "ru": "Не удалось сохранить контекст этой сессии — твой ответ не сохранён.", "es": "No se pudo guardar el contexto de esta sesión — tu respuesta no se ha guardado.", "de": "Der Kontext für diese Sitzung konnte nicht gespeichert werden — deine Antwort wurde nicht behalten.", "fr": "Impossible d’enregistrer le contexte de cette séance — ta réponse n’a pas été conservée.", "pt": "Não foi possível salvar o contexto desta sessão — a sua resposta não foi salva."},
    "data.delete.events": {
        'ja': '合図の記録',
        'zh': '提示记录',
        'ru': 'записи подсказок',
        'es': 'registros de avisos',
        'de': 'Aufgezeichnete Hinweise',
        'fr': 'enregistrements des rappels',
        'pt': 'registros de avisos',
    },
    "data.delete.tts": {
        'ja': '読み上げた合図（キャッシュ）',
        'zh': '语音提示（缓存）',
        'ru': 'озвученные подсказки (кэш)',
        'es': 'avisos hablados (caché)',
        'de': 'Gesprochene Hinweise (Cache)',
        'fr': 'rappels vocaux (cache)',
        'pt': 'avisos falados (cache)',
    },
    "data.delete.backup": {"ja": "バックアップ", "zh": "备份", "ru": "резервная копия", "es": "copia de seguridad", "de": "Sicherung", "fr": "sauvegarde", "pt": "cópia de segurança"},
    "history.col_minmax": {"ja": "最小 / 最大", "zh": "最小 / 最大", "ru": "Мин / макс", "es": "Min / max", "de": "Min / max", "fr": "Min / max", "pt": "Mín / máx"},
    # --- Session context: activity (played/worked) + own note ---
    "session.context.activity_question": {
        'sk': 'Hra, alebo práca?',
        'en': 'Were you playing or working?',
        'ja': '遊んでいた？それとも作業していた？',
        'zh': '你是在玩，还是在工作？',
        'ru': 'Игра или работа?',
        'es': '¿Estabas jugando o trabajando?',
        'de': 'Hast du gespielt oder gearbeitet?',
        'fr': 'Tu jouais ou tu travaillais ?',
        'pt': 'Você estava jogando ou trabalhando?',
    },
    "session.context.activity.play": {
        'sk': 'Hra',
        'en': 'Playing',
        'ja': 'ゲーム',
        'zh': '在玩',
        'ru': 'Игра',
        'es': 'Jugando',
        'de': 'Gespielt',
        'fr': 'Je jouais',
        'pt': 'Jogando',
    },
    "session.context.activity.work": {
        'sk': 'Práca',
        'en': 'Working',
        'ja': '作業',
        'zh': '在工作',
        'ru': 'Работа',
        'es': 'Trabajando',
        'de': 'Gearbeitet',
        'fr': 'Je travaillais',
        'pt': 'Trabalhando',
    },
    # 0.3: the thresholds are not learnt from a session in which the app was
    # only being set up (`hr_stats.ciste_relacie`, `setup`). After the
    # introduction the chip is turned on by the app.
    "session.context.setup": {"sk": "Len nastavovanie appky", "en": "Just setting up the app", "ja": "アプリの設定だけ", "zh": "只是在设置应用", "ru": "Только настройка приложения", "es": "Solo configurando la app", "de": "Nur die App eingerichtet", "fr": "Juste la configuration de l'app", "pt": "Só configurando o app"},
    "session.context.setup_hint": {"sk": "Z takej relácie sa neučím, čo je u teba pokoj a záťaž. V histórii ostane.", "en": "I won't learn your calm or your load from it. It stays in History.", "ja": "このセッションからは、あなたの平静や負荷を学びません。履歴には残ります。", "zh": "我不会从这次记录里学习你的平静和负荷。它仍会留在历史中。", "ru": "По такой сессии я не учусь, что для тебя покой и нагрузка. В истории она останется.", "es": "De una sesión así no aprendo tu calma ni tu carga. Se queda en el historial.", "de": "Aus so einer Sitzung lerne ich weder deine Ruhe noch deine Belastung. Im Verlauf bleibt sie.", "fr": "Je n’apprends ni ton calme ni ta charge d’une telle séance. Elle reste dans l’historique.", "pt": "Com uma sessão assim, não aprendo sua calma nem sua carga. Ela continua no histórico."},
    # The same sentence when the app turned the chip on by itself (the first
    # session after the introduction): the player must know why - and that
    # they should turn it off if they really played during it.
    "session.context.setup_hint_first": {"sk": 'Prvú reláciu po úvode som označila sama: neučím sa z nej, čo je u teba pokoj a záťaž, a v histórii ostane. Ak sa v nej naozaj hralo, odznač to.', "en": "I marked the first session after the intro myself: I won't learn your calm or your load from it, and it stays in History. If you actually played, untick it.", "ja": "案内のあとの最初のセッションは、私が自分で印を付けました。ここからはあなたの平静や負荷を学ばず、履歴には残ります。実際に遊んでいたなら、印を外してください。", "zh": "介绍之后的第一次记录是我自己标记的：我不会从中学习你的平静和负荷，它仍会留在历史中。如果你其实在玩，请取消标记。", "ru": 'Первую сессию после вступления я отметила сама: по ней я не учусь, что для тебя покой и нагрузка, а в истории она останется. Если в ней на самом деле шла игра, сними отметку.', "es": "La primera sesión después de la introducción la marqué yo misma: no aprendo de ella tu calma ni tu carga, y se queda en el historial. Si en realidad jugaste, desmárcala.", "de": "Die erste Sitzung nach der Einführung habe ich selbst markiert: Aus ihr lerne ich weder deine Ruhe noch deine Belastung, und im Verlauf bleibt sie. Wenn du wirklich gespielt hast, nimm die Markierung weg.", "fr": "J’ai marqué moi-même la première séance après l’intro : je n’en apprends ni ton calme ni ta charge, et elle reste dans l’historique. Si tu as vraiment joué, décoche-la.", "pt": "Marquei sozinha a primeira sessão depois da introdução: não aprendo com ela sua calma nem sua carga, e ela continua no histórico. Se você jogou de verdade, desmarque."},
    "session.context.note_label": {"sk": "Vlastná poznámka (nepovinné)", "en": "Your own note (optional)", "ja": "自由メモ（任意）", "zh": "自己的备注（可选）", "ru": "Своя заметка (необязательно)", "es": "Nota propia (opcional)", "de": "Eigene Notiz (optional)", "fr": "Note perso (facultatif)", "pt": "Sua nota (opcional)"},
    "hud.quick_label": {
        'sk': 'Panel tepu na obrazovke',
        'en': 'On-screen HR panel',
        'ja': '画面上の心拍パネル',
        'zh': '屏幕上的心率面板',
        'ru': 'Панель пульса на экране',
        'es': 'Panel de pulso en pantalla',
        'de': 'Puls-Panel auf dem Bildschirm',
        'fr': 'Panneau du pouls à l’écran',
        'pt': 'Painel de pulso na tela',
    },
    "history.export_col.activity": {"sk": "činnosť", "en": "activity", "ja": "活動", "zh": "活动", "ru": "активность", "es": "actividad", "de": "Aktivität", "fr": "activité", "pt": "atividade"},
    "history.export_col.hud_seen": {"sk": "HUD videný %", "en": "HUD seen %", "ja": "HUD表示率", "zh": "HUD可见%", "ru": "HUD виден %", "es": "HUD visto %", "de": "HUD sichtbar %", "fr": "HUD vu %", "pt": "HUD visto %"},
    "history.export_col.note": {"sk": "poznámka", "en": "note", "ja": "メモ", "zh": "备注", "ru": "заметка", "es": "nota", "de": "Notiz", "fr": "note", "pt": "nota"},
    # --- round 1 of variables: illness/sport before, sleep, subjective ---
    "session.context.illness": {
        'sk': 'choroba / necítim sa dobre',
        'en': 'feeling ill / off',
        'ja': '体調が悪い',
        'zh': '感觉不舒服/生病',
        'ru': 'нездоровится / болею',
        'es': 'enfermedad / me siento mal',
        'de': 'fühle mich krank / mies',
        'fr': 'je me sens malade / patraque',
        'pt': 'me sinto doente / mal',
    },
    "session.context.exercise_before": {
        'sk': 'pohyb pred hraním',
        'en': 'moved/exerted before playing',
        'ja': 'プレイ前に動いた/息が上がった',
        'zh': '玩之前运动/喘过气',
        'ru': 'движение перед игрой',
        'es': 'actividad física antes de jugar',
        'de': 'vor dem Spielen bewegt/außer Atem',
        'fr': 'activité physique avant de jouer',
        'pt': 'me mexi / fiquei ofegante antes de jogar',
    },
    "session.sleep.q": {"sk": "Spánok minulú noc", "en": "Sleep last night", "ja": "昨夜の睡眠", "zh": "昨晚的睡眠", "ru": "Сон прошлой ночью", "es": "Sueño anoche", "de": "Schlaf letzte Nacht", "fr": "Sommeil la nuit dernière", "pt": "Sono na noite passada"},
    "session.sleep.rested": {"sk": 'dobrý', "en": "rested", "ja": "よく寝た", "zh": "睡得好", "ru": 'хороший', "es": 'reparador', "de": "ausgeschlafen", "fr": 'réparateur', "pt": 'reparador'},
    "session.sleep.mid": {"sk": "stredne", "en": "so-so", "ja": "まあまあ", "zh": "一般", "ru": "средне", "es": "regular", "de": "mittel", "fr": "moyen", "pt": "mais ou menos"},
    "session.sleep.broken": {"sk": "rozbitý", "en": "broken", "ja": "ボロボロ", "zh": "很差", "ru": 'прерывистый', "es": "fatal", "de": "mies", "fr": "haché", "pt": "péssimo"},
    "session.felt.header": {"sk": "Ako sa to cítilo", "en": "How it felt", "ja": "どう感じた", "zh": "感觉如何", "ru": "Как это ощущалось", "es": "Cómo se sintió", "de": "Wie es sich anfühlte", "fr": "Ressenti", "pt": "Como você se sentiu"},
    "session.felt.load": {"sk": "Vnímaná záťaž", "en": "Perceived load", "ja": "感じた負荷", "zh": "主观强度", "ru": "Ощущаемая нагрузка", "es": "Carga percibida", "de": "Empfundene Last", "fr": "Charge ressentie", "pt": "Carga percebida"},
    "session.felt.load_hint": {"sk": "0 = úplný pokoj, 10 = maximálne vypätie", "en": "0 = totally calm, 10 = maxed out", "ja": "0＝完全に穏やか、10＝極限", "zh": "0＝完全平静，10＝极度紧绷", "ru": "0 = полный покой, 10 = на пределе", "es": "0 = calma total, 10 = al límite", "de": "0 = ganz ruhig, 10 = am Limit", "fr": "0 = tout calme, 10 = à fond", "pt": "0 = calma total, 10 = no limite"},
    "session.felt.valence": {"sk": "Bolo ti skôr dobre, či zle?", "en": "Did it feel good or bad?", "ja": "気分は良かった？悪かった？", "zh": "感觉是好还是坏？", "ru": "Было приятно или неприятно?", "es": "¿Te sentiste bien o mal?", "de": "Eher gut oder schlecht?", "fr": "Plutôt bien ou mal ?", "pt": "Foi mais para bom ou para ruim?"},
    "session.felt.valence.-2": {"sk": "zle", "en": "bad", "ja": "悪い", "zh": "差", "ru": "плохо", "es": "mal", "de": "schlecht", "fr": "mal", "pt": "ruim"},
    "session.felt.valence.-1": {"sk": "skôr zle", "en": "rather bad", "ja": "やや悪い", "zh": "偏差", "ru": "скорее плохо", "es": "algo mal", "de": "eher schlecht", "fr": "plutôt mal", "pt": "mais para ruim"},
    "session.felt.valence.0": {
        'sk': 'neutrálne',
        'en': 'neutral',
        'ja': 'ふつう',
        'zh': '一般',
        'ru': 'нейтрально',
        'es': 'neutral',
        'de': 'neutral',
        'fr': 'neutre',
        'pt': 'neutro',
    },
    "session.felt.valence.1": {"sk": "skôr dobre", "en": "rather good", "ja": "やや良い", "zh": "偏好", "ru": "скорее хорошо", "es": "algo bien", "de": "eher gut", "fr": "plutôt bien", "pt": "mais para bom"},
    "session.felt.valence.2": {"sk": "dobre", "en": "good", "ja": "良い", "zh": "好", "ru": "хорошо", "es": "bien", "de": "gut", "fr": "bien", "pt": "bom"},
    "session.felt.body_q": {"sk": "Keď to bolo najintenzívnejšie, telo bolo skôr…", "en": "At the most intense moment, your body was…", "ja": "一番きつかったとき、体はどうだった…", "zh": "最紧张的时候，身体更偏…", "ru": "В самый напряжённый момент тело было скорее…", "es": "En el momento más intenso, tu cuerpo estaba…", "de": "Im intensivsten Moment war dein Körper eher…", "fr": "Au moment le plus intense, ton corps était plutôt…", "pt": "No momento mais intenso, o corpo estava mais…"},
    "session.felt.body.ok": {"sk": "nič zvláštne", "en": "nothing special", "ja": "特に何も", "zh": "没什么特别", "ru": "ничего особого", "es": "nada especial", "de": "nichts Besonderes", "fr": "rien de spécial", "pt": "nada de especial"},
    "session.felt.body.flow": {
        'sk': 'sústredené (flow)',
        'en': 'focused (flow)',
        'ja': '集中(フロー)',
        'zh': '专注(心流)',
        'ru': 'сосредоточено (поток)',
        'es': 'concentrado (flow)',
        'de': 'fokussiert (Flow)',
        'fr': 'concentré (flow)',
        'pt': 'focado (flow)',
    },
    "session.felt.body.wired": {
        'sk': 'nabudené',
        'en': 'wired',
        'ja': 'そわそわ',
        'zh': '亢奋',
        'ru': 'на взводе',
        'es': 'acelerado',
        'de': 'aufgedreht',
        'fr': 'surexcité',
        'pt': 'ligado',
    },
    "session.felt.body.tense": {
        'sk': 'napäté (čeľusť, plecia)',
        'en': 'tense (jaw/shoulders)',
        'ja': '緊張(顎/肩)',
        'zh': '紧绷(下巴/肩)',
        'ru': 'напряжено (челюсть, плечи)',
        'es': 'tenso (mandíbula/hombros)',
        'de': 'verspannt (Kiefer/Schultern)',
        'fr': 'tendu (mâchoire/épaules)',
        'pt': 'tenso (maxilar/ombros)',
    },
    "session.felt.body.sick": {"sk": "zle od žalúdka", "en": "queasy stomach", "ja": "胃がむかむか", "zh": "反胃", "ru": "мутит в животе", "es": "revuelto el estómago", "de": "flau im Magen", "fr": "mal au ventre", "pt": "enjoo no estômago"},
    "session.felt.cue_q_fired": {
        'sk': 'Sadla pripomienka?',
        'en': 'Did the cue land?',
        'ja': '合図は響いた？',
        'zh': '提示到位吗？',
        'ru': 'Подсказка попала?',
        'es': '¿Encajó el aviso?',
        'de': 'Hat der Hinweis gepasst?',
        'fr': 'Le rappel a-t-il fait mouche ?',
        'pt': 'O aviso acertou?',
    },
    "session.felt.cue_q_silent": {"sk": "Bola chvíľa, keď sa mala ozvať?", "en": "Was there a moment it should have spoken up?", "ja": "声をかけるべき瞬間はあった？", "zh": "有该出声提醒的时刻吗？", "ru": "Был момент, когда стоило подсказать?", "es": "¿Hubo un momento en que debió avisar?", "de": "Gab es einen Moment, wo er sich hätte melden sollen?", "fr": "Y a-t-il eu un moment où il aurait dû se manifester ?", "pt": "Houve um momento em que devia ter avisado?"},
    "session.felt.cue.landed": {"sk": "sadla", "en": "it landed", "ja": "響いた", "zh": "到位", "ru": "попала", "es": "encajó", "de": "hat gepasst", "fr": "a touché", "pt": "acertou"},
    "session.felt.cue.unneeded": {"sk": "netreba bolo", "en": "wasn't needed", "ja": "不要だった", "zh": "没必要", "ru": "не нужна была", "es": "no hacía falta", "de": "war unnötig", "fr": "pas nécessaire", "pt": "não era preciso"},
    "session.felt.cue.disruptive": {"sk": "rušila", "en": "it disrupted", "ja": "邪魔だった", "zh": "打扰了", "ru": "мешала", "es": "molestó", "de": "hat gestört", "fr": "a gêné", "pt": "atrapalhou"},
    "session.felt.cue.missed": {"sk": "áno, mala", "en": "yes, it should have", "ja": "はい、あった", "zh": "有，该提醒", "ru": "да, стоило", "es": "sí, debió", "de": "ja, hätte sollen", "fr": "oui, il aurait dû", "pt": "sim, devia"},
    "history.export_col.sleep": {"sk": "spánok", "en": "sleep", "ja": "睡眠", "zh": "睡眠", "ru": "сон", "es": "sueño", "de": "Schlaf", "fr": "sommeil", "pt": "sono"},
    "history.export_col.felt_load": {"sk": "vnímaná záťaž", "en": "felt load", "ja": "感じた負荷", "zh": "主观强度", "ru": "ощущаемая нагрузка", "es": "carga percibida", "de": "empfundene Last", "fr": "charge ressentie", "pt": "carga percebida"},
    "history.export_col.valence": {"sk": "valencia", "en": "valence", "ja": "感情価", "zh": "效价", "ru": "валентность", "es": "valencia", "de": "Valenz", "fr": "valence", "pt": "valência"},
    "history.export_col.body_peak": {"sk": "telo v najintenzívnejšej chvíli", "en": "body at the most intense moment", "ja": "一番きつかったときの体", "zh": "最紧张时的身体", "ru": "тело в самый напряжённый момент", "es": "cuerpo en el momento más intenso", "de": "Körper im intensivsten Moment", "fr": "corps au moment le plus intense", "pt": "corpo no momento mais intenso"},
    "history.export_col.cue_verdict": {
        'sk': 'verdikt pripomienky',
        'en': 'cue verdict',
        'ja': '合図の評価',
        'zh': '提示评价',
        'ru': 'вердикт подсказки',
        'es': 'veredicto del aviso',
        'de': 'Hinweis-Urteil',
        'fr': 'verdict du rappel',
        'pt': 'veredito do aviso',
    },
    "history.export_col.confounded": {"sk": "skreslená?", "en": "confounded?", "ja": "撹乱？", "zh": "受干扰？", "ru": "искажена?", "es": "¿sesgada?", "de": "verfälscht?", "fr": "faussée ?", "pt": "enviesada?"},
}
for _k, _langs in _DOPLNENE_PREKLADY.items():
    STRINGS.setdefault(_k, {}).update(_langs)

STRINGS.setdefault("app.version_short", {}).update({
    "ja": "アルファ 0.3.1", "zh": "Alpha 0.3.1", "ru": "альфа 0.3.1",
    "es": "alfa 0.3.1", "pt": "alfa 0.3.1",
})

# --- 0.2 B3-worlds: two worlds, one body -------------------------------------
# Play and work have separate history, insights and look; the resting
# baseline is shared. SK/EN by hand, the other languages: _tr7 at the end
# of the file.
# The question in the questionnaire (played/worked) uses the existing
# keys `session.context.activity*` - nothing new.
#
# The four keys below (high heart rate limit, cue threshold) have a NEW
# wording here: since B3-worlds they are computed only from PLAY
# sessions, so the sentence "after N more sessions" would be a lie on
# work evenings. The old wordings and their translations were deleted,
# so that the old wording does not survive in any language.
STRINGS.update({
    'world.play': _sk_en('Hra', 'Play'),
    'world.work': _sk_en('Práca', 'Work'),
    'world.tip': _sk_en(
        'Svet: hra alebo práca — každý má vlastnú históriu a vzhľad.\nV práci sa ozývam len obrázkom. Bežiaca relácia ostáva vo svete, v ktorom začala.',
        'World: play or work — each keeps its own history and look.\nAt work I only show pictures. A running session stays in the world it started in.'),
    'settings.world': _sk_en('Svet', 'World'),
    'settings.world_sub': _sk_en(
        'Hra je Sumi, práca Aizome. Každý svet má vlastnú históriu a postrehy. V práci sa ozývam len obrázkom — bez hlasu a zvuku. Pokojová základňa je spoločná, telo je jedno; hranicu vysokého tepu aj prah záťaže počítam len z hrania.',
        'Play is Sumi, work is Aizome. Each world keeps its own history and insights. At work I only show pictures — no voice, no sound. The resting baseline is shared, it is one body; the high heart-rate limit and the load threshold are learned from play only.'),
    # 0.2 (ladder): the effectiveness chart counts only cues that sounded -
    # at work a cue is only a picture, so there is nothing left to count.
    'history.world_note': _sk_en(
        'Svet: {world}. Staršie relácie bez štítku patria do Hry. Graf „{chart}“ ráta len pripomienky z hry, ktoré zazneli — v práci sa ozývam len obrázkom.',
        'World: {world}. Older unlabelled sessions count as Play. The “{chart}” chart counts only play cues that made a sound — at work I only show a picture.'),
    'ob.step4.title': _sk_en('Vyber si hlavný svet', 'Pick your main world'),
    # 0.3: the last sentence - the app computes the limit and the threshold
    # only from Play (`DandurfApp.ALGORITMUS_SVET`), Work never teaches them.
    'ob.step4.body': _sk_en(
        'Prepneš ho kedykoľvek vpravo hore. Každý svet má vlastnú históriu '
        'aj vzhľad. Vlastné hranice sa učím len z Hry.',
        'Switch it any time at the top right. Each world keeps its own history '
        'and look. I learn your own limits from Play only.'),
    'ob.world.play.title': _sk_en('Hra · 墨 Sumi', 'Play · 墨 Sumi'),
    # „väčšinou“ (mostly): about a tenth of the cues stay silent on purpose
    # (comparison) and a cue whose pause does not come is only a picture -
    # „s hlasom aj obrazom“ (with voice and picture) promised more than the
    # app does.
    'ob.world.play.desc': _sk_en(
        'Keď hráš. Pripomienky v pauzách, väčšinou s hlasom.\nAtrament so zlatom.',
        'For playing. Cues in the pauses, mostly with voice.\nInk with gold.'),
    'ob.world.work.title': _sk_en('Práca · 藍 Aizome', 'Work · 藍 Aizome'),
    'ob.world.work.desc': _sk_en(
        'Keď pracuješ. Pripomienky len obrázkom, bez hlasu a zvuku.\nIndigo.',
        'For working. Pictures only, no voice or sound.\nIndigo.'),
    'session.end.title_work': _sk_en(
        'Za tebou je {time} práce.',
        'You worked for {time}.'),
    'session.end.cues_work': _sk_en(
        'Ozvala som sa {n}× — v práci len obrázkom, bez hlasu a zvuku.',
        'I spoke up {n}× — at work with a picture only, no voice or sound.'),
    'settings.hr_critical_computed': _sk_en(
        'Tvoja hranica vysokého tepu: {bpm} BPM — spočítala som ju z {n} tvojich herných relácií. Nenastavuje sa; upravím si ju, ako ťa budem spoznávať.',
        'Your high heart-rate limit: {bpm} BPM — I computed it from {n} of your play sessions. Not a setting; I adjust it as I get to know you.'),
    'settings.hr_critical_learning': _sk_en(
        'Hranica vysokého tepu: zatiaľ {bpm} BPM. Tvoju spočítam po ďalších {treba} herných reláciách, každá aspoň 5 minút.',
        'High heart-rate limit: {bpm} BPM for now. I’ll compute yours after {treba} more play sessions of at least 5 minutes each.'),
    'cue_rate.computed': _sk_en(
        'Ozvem sa, keď tvoja záťaž vydrží {hold} s nad prahom {prah} zo 100 — ten prah som si spočítala z {n} tvojich herných relácií ako úroveň, nad ktorou tráviš pätinu hrania. Najviac {strop}× za hodinu, odstup aspoň {odstup} min.',
        'I speak up when your load stays above the threshold of {prah}/100 for {hold} s — I computed that threshold from {n} of your play sessions as the level you spend a fifth of your playtime above. At most {strop}× per hour, at least {odstup} min apart.'),
    'cue_rate.learning': _sk_en(
        'Zatiaľ platia čísla priemerného hráča: ozvem sa, keď záťaž vydrží {hold} s nad prahom {prah} zo 100. Tvoj prah si spočítam z herných relácií.',
        'For now I use average-player numbers: I speak up when your load stays above the threshold of {prah}/100 for {hold} s. I’ll compute your own threshold from your play sessions.'),
})

# --- 0.2 cue ladder: the app turns itself down ---------------------------
# voice -> picture -> pause (`rebrik.py`). One quiet sentence in History,
# only when the ladder is below the top, and with the reason. The app
# speaks of itself in the feminine. SK/EN by hand, the other languages:
# _tr7 at the end of the file.
STRINGS.update({
    'session.felt.cue.agitated': _sk_en('rozhodila ma', 'it wound me up'),
    'history.rebrik.visual': _sk_en(
        'Teraz sa ozývam len obrázkom, bez zvuku. {dovod} Zvuk vrátim, keď ďalšie relácie s pripomienkou prejdú bez výhrad (treba ešte: {n}).',
        'For now I only show the picture, no sound. {dovod} I will bring the sound back once more sessions with a cue go by without a complaint (still needed: {n}).'),
    'history.rebrik.pause': _sk_en(
        'Pripomienky mám teraz vypnuté. {dovod} Obrázkom to skúsim znova po ďalších reláciách aspoň na 5 minút (treba ešte: {n}). Ak ti pripomienky chýbajú, v dotazníku po relácii odpovedz „áno, mala“ a od ďalšej relácie to skúsim znova.',
        'Cues are off for now. {dovod} I will try again with the picture after more sessions of at least 5 minutes (still needed: {n}). If you miss them, answer “yes, it should have” in the questionnaire after a session and I will try again from the next one.'),
    'history.rebrik.why.disruptive': _sk_en(
        'Po relácii stálo v dotazníku, že pripomienka rušila.',
        'After a session you said in the questionnaire that the cue got in the way.'),
    'history.rebrik.why.agitated': _sk_en(
        'Po relácii stálo v dotazníku, že ťa pripomienka rozhodila.',
        'After a session you said in the questionnaire that the cue wound you up.'),
    'history.rebrik.why.snooze': _sk_en(
        'Do minúty po pripomienke som bola stíšená a relácia potom ešte pokračovala.',
        'You snoozed me within a minute of a cue, and the session carried on after that.'),
    'history.rebrik.why.retry': _sk_en(
        'Po pár reláciách ticha to skúšam znova.',
        'After a few quiet sessions I am trying again.'),
    'history.rebrik.why.missed': _sk_en(
        'V dotazníku stálo, že som sa mala ozvať, tak to skúšam znova.',
        'You said I should have spoken up, so I am trying again.'),
    'session.end.cues_visual': _sk_en(
        'Ozvala som sa {n}× — len obrázkom, bez zvuku.',
        'I spoke up {n}× — as a picture only, no sound.'),
    'session.end.none_paused': _sk_en(
        'Pripomienky mám po tvojej spätnej väzbe na pár relácií vypnuté — prečo, nájdeš v Histórii. Ak ti chýbajú, odpovedz nižšie „áno, mala“.',
        'After your feedback I have switched cues off for a few sessions — History says why. If you miss them, answer “yes, it should have” below.'),
    'kamae.paused_sub': _sk_en(
        'Sledujem tep, ale pripomienky mám teraz vypnuté — prečo, nájdeš v Histórii.',
        'Watching your heart rate, but cues are off for now — History says why.'),
})

# --- 0.2 cue style: question in the onboarding and row in Settings ----------
# The question and the four answers were approved word for word by the
# author. The same three sentences (without "I don't know") are the
# values in Settings -> Sound, so that one choice does not have two
# names. The kicker of steps 1-4 changed to "of 5" (their _tr7 lines
# were deleted). SK/EN by hand, the other languages: _tr7 at the end of the
# file.
STRINGS.update({
    'ob.step5.kicker': _sk_en('KROK 5 z 5', 'STEP 5 of 5'),
    'ob.cue.title': _sk_en(
        'Keď ťa hra poriadne vytočí, ako chceš, aby sa appka ozvala?',
        'When a game really winds you up, how do you want the app to speak up?'),
    'ob.cue.voice': _sk_en('Pokojne aj hlasom', 'Voice is fine'),
    'ob.cue.sound': _sk_en('Radšej len zvuk a obrázok',
                           'Rather just a sound and a picture'),
    'ob.cue.visual': _sk_en('Len obrázok, nič nehovor', 'Just a picture, say nothing'),
    'ob.cue.unsure': _sk_en(
        'Neviem — začni hlasom a stíš sa, keď budeš prekážať',
        'Not sure — start with voice and go quieter if you get in the way'),
    'ob.cue.note': _sk_en(
        'Zmeníš to v Nastaveniach → Zvuk. Stíšiť sa viem aj sama, hlasnejšie nikdy. Zo začiatku asi každú štvrtú pripomienku schválne ukážem len obrázkom — na porovnanie.',
        'You can change this in Settings → Sound. I can go quieter on my own, never louder. At first, about one cue in four is picture-only on purpose — for comparison.'),
    # Quiet line under the question: what leaves the computer with the choice
    # "by voice". The same truth as `data.hint`; tab name =
    # nav.nastavenia_tabs.zvuk.
    'ob.cue.online_note': _sk_en(
        'Prirodzený hlas je online: texty pripomienok (nikdy nie tep) sa pošlú službe Microsoft na prevod do reči. Hlas z Windows neposiela nič — prepneš naň v Nastaveniach → Zvuk.',
        'The natural voice is online: the text of your cues (never your heart rate) is sent to Microsoft to be turned into speech. The Windows voice sends nothing — switch to it in Settings → Sound.'),
    'ob.cue.work_note': {
        'sk': 'V Práci sa ozývam len obrázkom — toto platí pre Hru.',
        'en': 'In Work I only show a picture — this is about Play.',
        'ja': '「仕事」では画像だけで知らせます — これは「ゲーム」の設定です。',
        'zh': '在“工作”里我只用图片提示——这里设置的是“游戏”。',
        'ru': 'В «Работе» я подаю знак только картинкой — это настройка для «Игры».',
        'es': 'En Trabajo solo aviso con una imagen — esto es para Juego.',
        'de': 'In Arbeit melde ich mich nur mit einem Bild — das hier gilt für Spiel.',
        'fr': 'En Travail, je ne me manifeste que par une image — ceci vaut pour Jeu.',
        'pt': 'No Trabalho eu só aviso com uma imagem — isto vale para o Jogo.',
    },
    'ob.preview.voice': {
        'sk': '▶ Ukážka (hlas z Windows — prirodzený je jemnejší)',
        'en': '▶ Preview (Windows voice — the natural one is softer)',
        'ja': '▶ 試聴（Windows の音声 — 自然な音声はもっとやわらか）',
        'zh': '▶ 试听（Windows 语音——自然语音更柔和）',
        'ru': '▶ Пример (голос Windows — естественный звучит мягче)',
        'es': '▶ Ejemplo (voz de Windows — la natural suena más suave)',
        'de': '▶ Hörprobe (Windows-Stimme — die natürliche klingt weicher)',
        'fr': '▶ Aperçu (voix Windows — la naturelle est plus douce)',
        'pt': '▶ Amostra (voz do Windows — a natural é mais suave)',
    },
    'ob.preview.sound': {
        'sk': '▶ Ukážka zvuku',
        'en': '▶ Preview the sound',
        'ja': '▶ 効果音を試聴',
        'zh': '▶ 试听音效',
        'ru': '▶ Послушать звук',
        'es': '▶ Escuchar el sonido',
        'de': '▶ Ton anhören',
        'fr': '▶ Écouter le son',
        'pt': '▶ Ouvir o som',
    },
    'ob.preview.visual': {
        'sk': '▶ Ukážka obrázka',
        'en': '▶ Preview the picture',
        'ja': '▶ 画像を見る',
        'zh': '▶ 看看图片',
        'ru': '▶ Показать картинку',
        'es': '▶ Ver la imagen',
        'de': '▶ Bild ansehen',
        'fr': '▶ Voir l’image',
        'pt': '▶ Ver a imagem',
    },
    'settings.cue_style': _sk_en('Ako sa ozývam', 'How I speak up'),
    'settings.cue_style_sub': _sk_en(
        'Toto je najviac, čo použijem — hlasnejšie nikdy. Keď pripomienky rušia (dotazník po hre alebo „teraz nie“), stíšim sa aj sama. V práci sa ozývam len obrázkom.',
        'This is the most I’ll use — never louder. When cues get in the way (the questionnaire after play, or “not now”), I go quieter on my own. At work, pictures only.'),
})

# --- 0.2 controller: input without a single pause ----------------------------
# A controller's gyroscope or a stick without a dead zone reports input to
# Windows non-stop and the app finds no pause (measured on the author's
# setup).
# A quiet line on Today once per session (`_tick_nonstop_input`) and a tip
# in the pairing guide. The same advice as `session.end.none_nopause`.
# SK/EN by hand, the other languages: _tr7 at the end of the file.
STRINGS.update({
    'dnes.nonstop_input': _sk_en(
        'Už {min} minút som nezachytila ani krátku pauzu vo vstupe — možno ho '
        'niečo hlási bez prestávky, napríklad pohybový senzor (gyro) ovládača '
        'alebo páčka bez mŕtvej zóny.',
        'For {min} minutes I have not caught even a short pause in your input '
        "— something may be reporting it nonstop, such as a controller's "
        'motion sensor (gyro) or a stick with no deadzone.'),
    'hr.trouble_pad': _sk_en(
        'Hráš s ovládačom? Gyro (pohybový senzor) mu vypni, ak ho nepoužívaš, '
        'a páčkam daj malú mŕtvu zónu. Inak môže ovládač hlásiť vstup bez '
        'prestávky a ja nenájdem pauzu, v ktorej by som sa ozvala.',
        'Playing with a controller? Turn off its gyro (motion sensor) if you '
        "don't use it, and give the sticks a small deadzone. Otherwise it may "
        'report input nonstop and I find no pause to speak up in.'),
})

# --- 24. 9. the author's decisions -------------------------------------------
# "Not now" silences only cues and measuring goes on (state in the middle
# of the Today page). The "How it sounds" preview follows the cue style -
# the sentence under it says what it will really do. SK/EN by hand, the
# other languages: _tr7 at the end of the file.
STRINGS.update({
    'kamae.snoozed': _sk_en('Mlčím', 'Keeping quiet'),
    # {combo} = the shortcut that really applies (0.3, batch 4); without it
    # `kamae.snoozed_sub_tray`. "Tou istou skratkou" (With the same shortcut)
    # was a lie when the registration failed or the shortcut was turned off.
    'kamae.snoozed_sub': _sk_en(
        '„Teraz nie“ platí do {until} — dovtedy sa neozvem, tep však merám '
        'ďalej. Skôr to zrušíš skratkou {combo} alebo v ponuke ikony v lište.',
        '“Not now” holds until {until} — I won’t speak up till then, but I '
        'keep measuring your heart rate. End it sooner with {combo} or from '
        'the tray icon’s menu.'),
    'settings.preview_sub_sound': _sk_en(
        'Prehrá zvuk prvej pripomienky tak, ako zaznie v hre, a ukáže jej obrázok. Bez slov — tak to máš nastavené v „Ako sa ozývam“.',
        'Plays the first cue’s sound the way it will sound in-game and shows its picture. No words — that is what you chose under “How I speak up”.'),
    'settings.preview_sub_visual': _sk_en(
        'Máš nastavený len obrázok, takže v hre nič nezaznie — pripomienka sa len ukáže. Tlačidlo ukáže obrázok prvej pripomienky.',
        'You chose just a picture, so nothing plays in-game — the cue is only shown. The button shows the first cue’s picture.'),
    # Preview in the "sound"/"picture" style when no enabled cue has an
    # in-game picture - then no cue would come in game at all.
    'log.preview_no_picture': _sk_en(
        'Ukážka: žiadna zapnutá pripomienka nemá zapnutý obrázok v hre, takže v tomto štýle by som sa v hre neozvala vôbec.',
        'Preview: no enabled cue has its in-game picture turned on, so in this style I would not show up in-game at all.'),
    # Post-session questionnaire after a session without a cue in which "not
    # now" applied - the state machine was asleep then and the other sentences
    # about the silence could be lies (`_preco_ticho`).
    'session.end.none_snoozed': _sk_en(
        '{min} min z relácie platilo tvoje „teraz nie“ — vtedy som mlčala, '
        'presne podľa tvojho želania.',
        'Your “not now” was on for {min} min of this session — I kept quiet '
        'then, as you asked.'),
})

# --- × in the title bar (0.2) ----------------------------------------------
# The cross does not quit the app, it only hides it in the tray - the
# port for the phone stays open and heart rate is still measured. The
# first time the app says so and offers a choice (`DandurfApp.on_close`).
# SK/EN by hand, the other 7 languages will come in the languages phase.
STRINGS.update({
    # The sentence stands ABOVE two buttons (Keep running in the tray / Quit
    # Zanshin, 0.3 batch 4) - the player has not chosen yet, so not "I keep
    # running", but what applies IF they let it run (0.3 batch 4b).
    'tray.close_first': _sk_en(
        'Ak ma necháš bežať v lište, ikona bude pri hodinách — ak ju nevidíš, je pod šípkou ^. Kým je zapnutý príjem tepu, port {port} ostáva otvorený pre telefón; kým som spustená (▶ na stránke Dnes), tep ďalej meriam a ukladám. Úplne ma potom vypneš pravým klikom na ikonu → Ukončiť.',
        'If you keep me running in the tray, my icon sits by the clock — if you don’t see it, it’s under the ^ arrow. While heart-rate receiving is on, port {port} stays open for your phone; while I’m started (▶ on the Today page), I keep measuring and saving your heart rate. To quit me completely later, right-click the icon → Quit.'),
})

# --- command palette (Ctrl+K) and translations note (0.2, languages phase) ---
# The palette had its texts hard-coded in Slovak (`_command_palette_items`,
# `ui_shell.CommandPalette`) - an English player saw „Navigácia“ and
# „Pomoc“ in it. The guide item is named like its panel
# (guide.panel_title). The sentence under the language picker says what
# is the source and what a translation; it shows in all languages. SK/EN
# by hand, the other languages: _tr7 at the end of the file.
STRINGS.update({
    'palette.placeholder': _sk_en(
        'Napíš názov stránky, profilu alebo pripomienky…',
        'Type the name of a page, profile or cue…'),
    'palette.replay_intro': _sk_en('Ukázať úvod znova', 'Show the intro again'),
    'palette.profile': _sk_en('Profil — {name}', 'Profile — {name}'),
    'palette.cat.help': _sk_en('Pomoc', 'Help'),
    'palette.cat.nav': _sk_en('Navigácia', 'Navigation'),
    'palette.cat.sound': _sk_en('Zvuk', 'Sound'),
    'palette.cat.app': _sk_en('Appka', 'App'),
    'palette.cat.profiles': _sk_en('Profily', 'Profiles'),
    'settings.language_note': _sk_en(
        'Appka je písaná po slovensky. Ostatné jazyky sú preklady s pomocou AI '
        'a rodený hovoriaci ich ešte nekontroloval — ak vidíš chybu, daj vedieť.',
        'The app is written in Slovak. Other languages are AI-assisted '
        'translations not yet checked by a native speaker — if you spot a '
        'mistake, let me know.'),
})


# ==========================================================================
# 0.2 LANGUAGES PHASE - translation of the keys from `_sk_en` into ja / zh /
# ru / es / de / fr / pt
# ==========================================================================
#
# Keys with sk/en by hand (`_sk_en`) had the other 7 languages in English
# - here is their translation (the source is SK, EN helps with the
# meaning). Keys that are in STRINGS as a full dict have the translation
# right in it, and `history.export_extra` has a fixed line in the batch
# above (before, a literal backslash+n instead of a new line). None of
# these keys has another `_tr7` line, so that an old translation could
# not silently survive under the new one.
#
# The translations are made with the help of AI (Claude) and a native
# speaker has not checked them yet (`settings.language_note`).

_tr7('settings.auto_profile', '知っているゲームが動いていたら、自分でプロファイルを切り替えて見守りを始める', '遇到我认识的游戏时，我会自己切换配置文件并开始关注', 'При знакомой игре сама переключу профиль и начну наблюдение', 'Con un juego que conozco, cambio de perfil y empiezo a observar yo sola', 'Bei einem Spiel, das ich kenne, wechsle ich selbst das Profil und starte die Beobachtung', 'Avec un jeu que je connais, je change de profil et je lance l’observation toute seule', 'Com um jogo que eu conheço, troco de perfil e começo a observar sozinha')
_tr7('slots.hint', 'いつ合図を出すかは、あなたの心拍が決めます：負荷がしばらく高いまま続いたら、もう上がっていない合間を待ちます。「ピーク」ゾーンでは黙っています。ここでは、私が話す内容を設定します。', '什么时候提醒你，由你的心率决定：负荷持续偏高一阵子后，我会等它不再上升的停顿；在“高峰”区间我保持安静。这里设置的是我要说什么。', 'Когда подать знак, решает твой пульс: если нагрузка какое-то время держится высокой, я жду паузу, в которой она уже не растёт; в зоне «Пик» я молчу. Здесь ты задаёшь, что я скажу.', 'Cuándo aviso lo decide tu pulso: si la carga se mantiene alta un rato, espero una pausa en la que ya no suba; en la zona Pico me callo. Aquí eliges qué digo.', 'Wann ich mich melde, entscheidet dein Puls: Bleibt deine Last eine Weile oben, warte ich auf eine Pause, in der sie nicht mehr steigt; in der Zone Spitze schweige ich. Hier stellst du ein, was ich sage.', 'C’est ton pouls qui décide quand je me manifeste : si ta charge reste haute un moment, j’attends une pause où elle ne monte plus ; dans la zone Pic, je me tais. Ici, tu règles ce que je dis.', 'Quem decide quando eu aviso é o seu pulso: se a carga fica alta por um tempo, espero uma pausa em que ela já não esteja subindo; na zona Pico fico calada. Aqui você define o que eu digo.')
_tr7('hr.step2_body', 'Android / Wear OS：Google Play の「HeartRateOnStream for OBS」（無料）。iPhone / Apple Watch：App Store の「PulseOSC」（有料、まだ未検証 — 作者は Apple 製品を持っていません）。アドレスとポート（ステップ 3）はどちらのアプリにも入力します。パスワード、シーン、ソースは Android のアプリだけに関係します — iPhone ではステップ 4 を飛ばしてください。下のコードを読み取り、アプリを時計とつないでください。', 'Android / Wear OS：Google Play 上的“HeartRateOnStream for OBS”（免费）。iPhone / Apple Watch：App Store 上的“PulseOSC”（付费，尚未测试——作者没有苹果设备）。两个应用都要填写地址和端口（第 3 步）。密码、场景和来源只适用于 Android 应用——用 iPhone 时请跳过第 4 步。扫描下面的二维码，把应用和手表连起来。', 'Android / Wear OS: «HeartRateOnStream for OBS» из Google Play (бесплатно). iPhone / Apple Watch: «PulseOSC» из App Store (платное, пока не проверено — у автора нет устройств Apple). Адрес и порт (шаг 3) нужны в обоих приложениях. Пароль, сцена и источник относятся только к приложению для Android — на iPhone шаг 4 пропусти. Отсканируй код ниже и свяжи приложение с часами.', 'Android / Wear OS: «HeartRateOnStream for OBS» de Google Play (gratis). iPhone / Apple Watch: «PulseOSC» de la App Store (de pago, sin probar todavía: el autor no tiene Apple). La dirección y el puerto (paso 3) van en las dos apps. La contraseña, la escena y la fuente son solo para la app de Android: en el iPhone, sáltate el paso 4. Escanea un código de abajo y conecta la app con el reloj.', 'Android / Wear OS: „HeartRateOnStream for OBS“ aus Google Play (kostenlos). iPhone / Apple Watch: „PulseOSC“ aus dem App Store (kostenpflichtig, bisher ungetestet — der Autor hat kein Apple-Gerät). Adresse und Port (Schritt 3) brauchen beide Apps. Passwort, Szene und Quelle gelten nur für die Android-App — auf dem iPhone überspringst du Schritt 4. Scanne unten einen Code und verbinde die App mit deiner Uhr.', 'Android / Wear OS : « HeartRateOnStream for OBS » sur Google Play (gratuit). iPhone / Apple Watch : « PulseOSC » sur l’App Store (payant, pas encore testé — l’auteur n’a pas d’appareil Apple). L’adresse et le port (étape 3) vont dans les deux apps. Le mot de passe, la scène et la source ne concernent que l’app Android — sur iPhone, saute l’étape 4. Scanne un code ci-dessous et relie l’app à ta montre.', 'Android / Wear OS: “HeartRateOnStream for OBS” na Google Play (grátis). iPhone / Apple Watch: “PulseOSC” na App Store (pago, ainda não testado — o autor não tem Apple). O endereço e a porta (passo 3) vão nos dois apps. Senha, cena e fonte valem só para o app de Android — no iPhone, pule o passo 4. Escaneie um código abaixo e conecte o app ao relógio.')
_tr7('history.empty', 'まだセッションはありません。時計をつなぎ（{page} → 時計のつなぎ方…）、「今日」ページの ▶ で私を開始して、1分以上プレイしてください — 停止すると、ここにセッションが表示されます。', '还没有任何记录。先连接手表（{page} → 如何连接手表…），在「今天」页面点 ▶ 启动我，然后至少玩一分钟——停止后，记录就会出现在这里。', 'Пока нет ни одной сессии. Подключи часы («{page}» → «Как подключить часы…»), запусти меня кнопкой ▶ на странице «Сегодня» и поиграй хотя бы минуту — после остановки сессия появится здесь.', 'Aún no hay sesiones. Vincula el reloj ({page} → Cómo vincular tu reloj…), iníciame con ▶ en la página Hoy y juega al menos un minuto: al detenerme, la sesión aparecerá aquí.', 'Noch keine Sitzung. Verbinde deine Uhr ({page} → Uhr verbinden…), starte mich mit ▶ auf der Seite Heute und spiel mindestens eine Minute — nach dem Stoppen erscheint die Sitzung hier.', 'Pas encore de séance. Connecte ta montre ({page} → Comment connecter ta montre…), lance-moi avec ▶ sur la page Aujourd’hui et joue au moins une minute — une fois arrêtée, la séance apparaît ici.', 'Ainda não há sessões. Pareie o relógio ({page} → Como parear o seu relógio…), me inicie com ▶ na página Hoje e jogue pelo menos um minuto — quando você parar, a sessão aparece aqui.')
_tr7('history.insights_note', 'このワールドの履歴から、バックグラウンドで算出しています。気づきとヒントであって、診断ではありません。', '在后台根据这个世界的历史计算。这些是观察和建议，不是诊断。', 'Считается в фоне по истории этого мира. Это наблюдения и советы, а не диагнозы.', 'Se calcula en segundo plano a partir del historial de este mundo. Son observaciones y consejos, no diagnósticos.', 'Wird im Hintergrund aus dem Verlauf dieser Welt berechnet. Das sind Beobachtungen und Tipps, keine Diagnosen.', 'C’est calculé en arrière-plan à partir de l’historique de ce monde. Ce sont des observations et des conseils, pas des diagnostics.', 'Calculado em segundo plano a partir do histórico deste mundo. São observações e dicas, não diagnósticos.')
_tr7('history.col_triggers', '合図', '提示', 'Подсказки', 'Avisos', 'Hinweise', 'Rappels', 'Avisos')
_tr7('origin.title', '生まれたいきさつ', '它是怎么来的', 'Как это появилось', 'Cómo nació', 'Wie es entstand', 'Comment c’est né', 'Como surgiu')
_tr7('origin.text', '僕も同じ世代の多くの人と同じように、ゲームと一緒に育ちました。目の奥では、外から見えるよりずっと多くのことが起きています。Zanshin は、それを平和なやり方で試してみようという僕なりの試みです。気づいてくれて、何も求めず、何も売らないもの。\n\nZanshin は何も新しいものを発明していません。心拍、ストレス、呼吸についての公開された研究と、ほかの人たちが開いたまま残してくれた道具の上に立っています。僕は AI の助けを借りてこれを作り、自分がゲームをする夜に調整してきました。これはアルファ版で、まだテスト中です — だからアプリはセッションのあとに合図が響いたかどうかを尋ねますし、最初はおよそ4回に1回、のちには10回に1回、合図がわざと黙ります。合図が本当に役立っているかを比べられるようにするためです。負荷は、心拍から本当にわかる3つのことを合わせた、あくまで組み合わせの指標です。安静時よりどれだけ上にいるか、心拍がどれだけ速く上がっているか、どれだけ長く高いままか。最初の数晩が過ぎると、アプリはしきい値をあなた自身のセッションから算出します。これは医療機器ではなく、誰も臨床的に検証していません。', '我和很多同龄人一样，是玩着游戏长大的。在我们眼睛背后发生的事，比看得见的要多。Zanshin 是我以平和的方式去尝试的一次努力：一个会留意、什么都不要、什么也不卖的东西。\n\nZanshin 并没有发明什么新东西。它建立在关于心率、压力和呼吸的公开研究之上，也建立在别人开放出来的工具之上。我借助 AI 把它做出来，并在自己玩游戏的一个个晚上里调校它。它还是 alpha 版，仍在测试中——这也是为什么每次记录结束后应用会问你提示是否到位，以及为什么一开始大约每四条、之后每十条提示里会有一条故意不出声，好比较提示是否真的有帮助。负荷是一个明确承认的组合，由心率真正能看出来的三件事构成：你比自己的平静水平高多少、心率上升得多快、在高位停留多久。前几个晚上之后，应用会根据你自己的记录计算阈值。它不是医疗器械，也没有人对它做过临床验证。', 'Я вырос с играми, как многие из моего поколения. За глазами в нас происходит больше, чем видно. Zanshin — моя попытка попробовать это мирно: нечто, что замечает, ничего не хочет и ничего не продаёт.\n\nZanshin не придумал ничего нового. Он опирается на общедоступные исследования пульса, стресса и дыхания и на инструменты, которые другие оставили открытыми. Я построил его с помощью ИИ и настраивал на собственных игровых вечерах. Это альфа, и она всё ещё тестируется — поэтому приложение после сессии спрашивает тебя, попала ли подсказка, а поначалу примерно каждая четвёртая, позже каждая десятая подсказка намеренно молчит, чтобы можно было сравнить, действительно ли подсказки помогают. Нагрузка — открыто признанное сочетание трёх вещей, которые по пульсу действительно можно определить: насколько ты выше своего покоя, как быстро растёт пульс и как долго он держится наверху. После первых нескольких вечеров пороги приложение считает по твоим собственным сессиям. Это не медицинское изделие, и никто не проверял его клинически.', 'Crecí con los videojuegos, como mucha gente de mi generación. Detrás de los ojos pasa más de lo que nadie ve. Zanshin es mi intento de probarlo en paz: algo que se da cuenta, no pide nada y no vende nada.\n\nZanshin no ha inventado nada nuevo. Se apoya en la investigación pública sobre el pulso, el estrés y la respiración, y en herramientas que otros dejaron abiertas. Lo construí con ayuda de la IA y lo fui afinando en mis propias noches de juego. Es una alfa y todavía se está probando — por eso la app te pregunta después de cada sesión si el aviso encajó, y al principio más o menos uno de cada cuatro avisos, más tarde uno de cada diez, se calla a propósito, para poder comparar si los avisos ayudan de verdad. La carga es una mezcla, reconocida abiertamente, de tres cosas que el pulso sí permite saber: cuánto estás por encima de tu reposo, lo rápido que sube el pulso y cuánto tiempo se mantiene alto. Tras las primeras noches, la app calcula los umbrales a partir de tus propias sesiones. No es un producto sanitario y nadie la ha validado clínicamente.', 'Ich bin mit Games aufgewachsen, wie viele aus meiner Generation. Hinter den Augen passiert mehr, als irgendwer sieht. Zanshin ist mein Versuch, es im Frieden zu probieren: etwas, das hinschaut, nichts will und nichts verkauft.\n\nZanshin hat nichts Neues erfunden. Es steht auf öffentlicher Forschung zu Puls, Stress und Atmung und auf Werkzeugen, die andere offen gelassen haben. Ich habe es mit Hilfe von KI gebaut und an meinen eigenen Spieleabenden abgestimmt. Es ist eine Alpha und wird noch getestet — auch deshalb fragt dich die App nach einer Sitzung, ob der Hinweis gepasst hat, und anfangs bleibt etwa jeder vierte, später jeder zehnte Hinweis absichtlich still, damit sich vergleichen lässt, ob die Hinweise wirklich helfen. Die Last ist eine offen eingestandene Mischung aus drei Dingen, die sich aus dem Puls wirklich ablesen lassen: wie weit du über deiner Ruhe bist, wie schnell der Puls steigt und wie lange er oben bleibt. Die Grenzen berechnet die App nach den ersten paar Abenden aus deinen eigenen Sitzungen. Es ist kein Medizinprodukt, und niemand hat es klinisch geprüft.', 'J’ai grandi avec les jeux vidéo, comme beaucoup de ma génération. Derrière les yeux, il se passe plus de choses que ce que l’on voit. Zanshin, c’est ma tentative d’essayer en paix : quelque chose qui remarque, ne demande rien et ne vend rien.\n\nZanshin n’a rien inventé de nouveau. Il repose sur la recherche publique sur le pouls, le stress et la respiration, et sur des outils que d’autres ont laissés ouverts. Je l’ai construit avec l’aide de l’IA et je l’ai peaufiné au fil de mes propres soirées de jeu. C’est une alpha, toujours en test — c’est aussi pour ça que l’app te demande après une séance si le rappel a touché, et qu’au début environ un rappel sur quatre, plus tard un sur dix, reste volontairement silencieux, pour pouvoir comparer si les rappels aident vraiment. La charge est un mélange assumé de trois choses que le pouls permet vraiment de savoir : de combien tu es au-dessus de ton niveau de repos, à quelle vitesse ton pouls monte et combien de temps il reste haut. Après les premières soirées, l’app calcule ses seuils à partir de tes propres séances. Ce n’est pas un dispositif médical, et personne ne l’a validée cliniquement.', 'Cresci com os jogos, como muita gente da minha geração. Por trás dos olhos acontece mais do que se vê. O Zanshin é a minha tentativa de tentar isso em paz: algo que percebe, não quer nada e não vende nada.\n\nO Zanshin não inventou nada de novo. Ele se apoia em pesquisas públicas sobre frequência cardíaca, estresse e respiração, e em ferramentas que outros deixaram abertas. Eu o construí com a ajuda de IA e o ajustei ao longo das minhas próprias noites de jogo. É uma versão alfa e ainda está em teste — é também por isso que, depois de uma sessão, o app te pergunta se o aviso acertou, e que no começo mais ou menos um aviso em cada quatro, e depois um em cada dez, fica em silêncio de propósito, para dar para comparar se os avisos realmente ajudam. A carga é uma mistura assumida de três coisas que dá para saber de verdade pelo pulso: quanto você está acima do seu repouso, com que rapidez o pulso sobe e por quanto tempo ele fica alto. Depois das primeiras noites, o app calcula os limites a partir das suas próprias sessões. Não é um dispositivo médico e ninguém o validou clinicamente.')
_tr7('origin.examples', 'よりどころにしている例をいくつか：', '它所依据的几个例子：', 'Несколько примеров, на которые он опирается:', 'Algunos ejemplos en los que se apoya:', 'Ein paar Beispiele, auf die es sich stützt:', 'Quelques exemples sur lesquels il s’appuie :', 'Alguns exemplos em que ele se apoia:')
_tr7('origin.full_list', '出典の全リストは GitHub の ZDROJE.md にあります。', '完整的来源列表在 GitHub 上的 ZDROJE.md 里。', 'Полный список источников — на GitHub в ZDROJE.md.', 'La lista completa de fuentes está en GitHub, en ZDROJE.md.', 'Die vollständige Liste der Quellen steht auf GitHub in ZDROJE.md.', 'La liste complète des sources est sur GitHub, dans ZDROJE.md.', 'A lista completa de fontes está no GitHub, em ZDROJE.md.')
_tr7('metric.breath.tag', '合図', '提示', 'подсказки', 'avisos', 'Hinweise', 'rappels', 'avisos')
_tr7('metric.session_len.tag', 'セッション', '记录', 'сессия', 'sesión', 'Sitzung', 'séance', 'sessão')
_tr7('metric.last_cue.tag', '合図から', '距提示', 'с подсказки', 'desde aviso', 'seit Hinweis', 'depuis le rappel', 'desde o aviso')
_tr7('metric.calm_time.tag', '平静', '平静', 'в покое', 'en calma', 'in Ruhe', 'au calme', 'em calma')
_tr7('metric.signal.tag', '信号', '信号', 'сигнал', 'señal', 'Signal', 'signal', 'sinal')
_tr7('metric.felt_vs_measured.tag', '感覚/計測', '感受/测量', 'ощущ./измер.', 'sentido/medido', 'gefühlt/gemessen', 'ressenti/mesuré', 'sentido/medido')
_tr7('metric.load.short', '心拍が安静時よりどれだけ上か、どれだけ速く上がるか、どれだけ長くそこにとどまるか — HRV ではなく心拍から。', '你的心率比平静水平高多少、上升多快、在那里停留多久——依据心率，而不是 HRV。', 'Насколько твой пульс выше твоего покоя, как быстро он растёт и как долго там держится — по пульсу, а не по HRV.', 'Cuánto está tu pulso por encima de tu reposo, lo rápido que sube y cuánto tiempo se mantiene ahí — a partir del pulso, no de la HRV.', 'Wie weit dein Puls über deiner Ruhe liegt, wie schnell er steigt und wie lange er dort bleibt — aus dem Puls, nicht aus HRV.', 'À quel point ton pouls est au-dessus de ton niveau de repos, à quelle vitesse il monte et combien de temps il y reste — d’après le pouls, pas la VFC.', 'Quanto o seu pulso está acima do seu repouso, com que rapidez sobe e por quanto tempo fica lá — pelo pulso, não pela HRV.')
_tr7('metric.load.more', '負荷のバーは、心拍から実際にわかる3つのことを組み合わせています。安静時よりどれだけ上か、どれだけ速く上がっているか、どれだけ長く高いままか。安静時の値は今夜だけでなく、あなたの穏やかだった夜からも取ります — 今日は高めから始まっている（コーヒー、暑さ、疲れ）なら、バーはゲームだけでなくそれも映します。バーの上の言葉は、今この瞬間の心拍の位置だけを示します。「やや上昇」は安静時より 10 BPM 上から、「高い」は 25 BPM から、「ピーク」はあなたの高心拍の上限からです。あなたのセッションが十分たまるまでは、安静時の値は今夜だけから取り、平均的なプレイヤー向けの上限を使います。この言葉が合図を出すわけではありません。負荷が「合図」ページのしきい値を超えると、私はまずそれがしばらく続くかを数え、そのあとで、負荷がもう上がっていないゲームの合間を待ちます。言葉が「ピーク」を示している間、私は黙っています。これは HRV でも診断でもありません。', '负荷条由心率真正能看出来的三件事组成：你比平静水平高多少、心率上升多快、在高位停留多久。平静水平我取自你较平静的那些晚上，而不只是今晚——如果你今天的起点就偏高（咖啡、炎热、疲劳），负荷条也会显示出来，而不只反映游戏。负荷条上方的词只说明你的心率此刻处在哪里：“略高”从比平静水平高 10 BPM 开始，“偏高”从高 25 BPM 开始，“高峰”则从你的高心率上限开始。在我积累足够多你的记录之前，平静水平只取今晚的数据，上限则用普通玩家的数值。这个词不会触发提示：当负荷越过“提示”页面上的负荷阈值时，我会先计时，看它能否在那里停留一阵子，然后才等待游戏中负荷不再上升的间歇。这个词显示“高峰”时，我保持安静。这不是 HRV，也不是诊断。', 'Полоса нагрузки складывается из трёх вещей, которые по пульсу действительно можно определить: насколько ты выше покоя, как быстро растёт пульс и как долго он держится наверху. Покой я беру из твоих более спокойных вечеров, а не только из сегодняшнего — если сегодня ты начинаешь выше (кофе, жара, усталость), полоса покажет и это, а не только игру. Слово над полосой говорит только о том, где твой пульс прямо сейчас: «Повышенная» — от 10 BPM выше покоя, «Высокая» — от 25 BPM, а «Пик» — от твоей границы высокого пульса. Пока у меня мало твоих сессий, покой я беру только из сегодняшнего вечера, а границу — для среднего игрока. Слово подсказку не запускает: когда нагрузка переходит порог со страницы «Подсказки», я сначала считаю, продержится ли она там какое-то время, и только потом жду паузы в игре, в которой нагрузка уже не растёт. Пока слово показывает «Пик», я молчу. Это не HRV и не диагноз.', 'La barra de carga combina tres cosas que el pulso sí permite saber: cuánto estás por encima de tu reposo, lo rápido que sube el pulso y cuánto tiempo se mantiene alto. Tu reposo lo tomo de tus noches más tranquilas, no solo de la de hoy — si hoy empiezas más alto (café, calor, cansancio), la barra también lo mostrará, no solo el juego. La palabra sobre la barra solo indica dónde está tu pulso ahora mismo: «Elevada» empieza 10 BPM por encima de tu reposo, «Alta» a partir de 25 BPM y «Pico» a partir de tu límite de pulso alto. Mientras no tenga suficientes sesiones tuyas, tomo el reposo solo de la noche de hoy y uso el límite de un jugador medio. La palabra no dispara el aviso: cuando la carga supera el umbral de la página Avisos, primero cuento si se mantiene ahí un rato, y solo entonces espero una pausa en el juego en la que la carga ya no suba. Mientras la palabra dice «Pico», guardo silencio. No es HRV ni un diagnóstico.', 'Der Lastbalken setzt sich aus drei Dingen zusammen, die sich aus dem Puls wirklich ablesen lassen: wie weit du über deiner Ruhe bist, wie schnell der Puls steigt und wie lange er oben bleibt. Deine Ruhe nehme ich aus deinen ruhigeren Abenden, nicht nur aus dem heutigen — wenn du heute höher startest (Kaffee, Hitze, Müdigkeit), zeigt der Balken auch das, nicht nur das Spiel. Das Wort über dem Balken sagt nur, wo dein Puls gerade steht: „Erhöht“ gilt ab 10 BPM über deiner Ruhe, „Hoch“ ab 25 BPM und „Spitze“ ab deiner Grenze für hohen Puls. Solange ich nicht genug Sitzungen von dir habe, nehme ich die Ruhe nur aus dem heutigen Abend und die Grenze eines durchschnittlichen Spielers. Das Wort löst keinen Hinweis aus: Wenn die Last die Schwelle von der Seite Hinweise überschreitet, zähle ich zuerst, ob sie eine Weile dort bleibt, und warte erst dann auf eine Pause im Spiel, in der die Last nicht mehr steigt. Solange das Wort „Spitze“ zeigt, schweige ich. Das ist weder HRV noch eine Diagnose.', 'La barre de charge combine trois choses que le pouls permet vraiment de savoir : de combien tu es au-dessus de ton niveau de repos, à quelle vitesse ton pouls monte et combien de temps il reste haut. Ton niveau de repos, je le tire de tes soirées plus calmes, pas seulement de celle d’aujourd’hui — si tu commences plus haut aujourd’hui (café, chaleur, fatigue), la barre le montre aussi, pas seulement le jeu. Le mot au-dessus de la barre dit seulement où se trouve ton pouls en ce moment : « Élevée » commence à 10 BPM au-dessus de ton niveau de repos, « Haute » à 25 BPM et « Pic » à ta limite de pouls élevé. Tant que je n’ai pas assez de tes séances, je prends ton niveau de repos de ce soir seulement, et une limite pour un joueur moyen. Le mot ne déclenche pas le rappel : quand la charge franchit le seuil de la page Rappels, je compte d’abord si elle s’y maintient un moment, et seulement ensuite j’attends une pause dans le jeu où la charge ne monte plus. Tant que le mot affiche « Pic », je me tais. Ce n’est ni la VFC ni un diagnostic.', 'A barra de carga combina três coisas que dá para saber de verdade pelo pulso: quanto você está acima do repouso, com que rapidez o pulso sobe e por quanto tempo fica alto. O repouso eu tiro das suas noites mais calmas, não só da de hoje — se hoje você começa mais alto (café, calor, cansaço), a barra mostra isso também, não só o jogo. A palavra acima da barra fala apenas de onde o seu pulso está agora: “Elevada” começa 10 BPM acima do repouso, “Alta” a partir de 25 BPM e “Pico” a partir do seu limite de pulso alto. Enquanto eu não tiver sessões suas suficientes, tiro o repouso só da noite de hoje e uso um limite de jogador médio. A palavra não dispara o aviso: quando a carga passa o limiar da página Avisos, primeiro conto se ela se mantém ali por um tempo, e só depois espero uma pausa no jogo em que a carga já não esteja subindo. Enquanto a palavra mostra “Pico”, fico em silêncio. Não é HRV nem diagnóstico.')
_tr7('metric.hrr.more', '緊張した場面のあと、どれだけ速く下がってくるかのおおまかな目安です。下がり幅が大きい = 早く平静に戻る。ふつうのゲーム中のピークから算出するもので、運動負荷テストではありません — 体力の成績ではなく、時間を通じた自分自身の傾向として見てください。', '粗略反映你在紧张之后多快回落。下降越多 = 越快回到平静。它是根据普通的游戏峰值计算的，不是运动负荷测试——把它当作你自己随时间变化的趋势，而不是体能评分。', 'Приблизительная картина того, как быстро ты возвращаешься вниз после напряжения. Больший спад = быстрее обратно к покою. Считается по обычным игровым пикам, а не по нагрузочному тесту — воспринимай это как свой собственный тренд во времени, а не как оценку физической формы.', 'Una imagen aproximada de lo rápido que vuelves a bajar después de un momento de tensión. Una caída mayor = vuelta más rápida a la calma. Se calcula a partir de los picos normales del juego, no de una prueba de esfuerzo — tómalo como tu propia tendencia en el tiempo, no como una nota de tu forma física.', 'Ein grobes Bild davon, wie schnell du nach einer Anspannung wieder runterkommst. Größerer Abfall = schneller zurück zur Ruhe. Berechnet aus gewöhnlichen Spitzen beim Spielen, nicht aus einem Belastungstest — sieh es als deinen eigenen Trend über die Zeit, nicht als Note für deine Fitness.', 'Une image approximative de la vitesse à laquelle tu redescends après un moment intense. Une plus grande baisse = retour au calme plus rapide. Le calcul part des pics de jeu ordinaires, pas d’un test d’effort — vois-y ta propre tendance dans le temps, pas une note de forme.', 'Uma ideia aproximada de quão rápido você volta a descer depois de um momento tenso. Queda maior = volta mais rápida à calma. É calculado a partir de picos comuns de jogo, não de um teste de esforço — encare como a sua própria tendência ao longo do tempo, não como nota de condicionamento físico.')
_tr7('metric.zones.more', 'ヘッドショットのあとの短いピークはふつうのことです。上限を超えている時間が長いなら、ゲームがあなたを緊張させ続けているのかもしれません。', '爆头后的短暂峰值很正常。长时间处于上限以上，可能说明游戏让你一直处于紧绷状态。', 'Короткие пики после хедшота — это нормально. Долгое время выше границы может значить, что игра держит тебя в напряжении.', 'Los picos breves después de un headshot son normales. Mucho tiempo por encima del límite puede significar que el juego te mantiene en tensión.', 'Kurze Spitzen nach einem Headshot sind normal. Lange Zeit über der Grenze kann bedeuten, dass dich das Spiel unter Spannung hält.', 'De courts pics après un headshot sont normaux. Beaucoup de temps au-dessus de la limite peut vouloir dire que le jeu te maintient sous tension.', 'Picos curtos depois de um headshot são normais. Muito tempo acima do limite pode significar que o jogo te mantém em tensão.')
_tr7('dashboard.picker_hint', '「今日」にはカードが4枚入ります。カードを別のカードにドラッグすると、場所が入れ替わります。', '“今天”页面能放 4 张卡片。把一张卡片拖到另一张上即可调整顺序——两者会互换位置。', 'На «Сегодня» помещаются 4 карточки. Порядок меняешь, перетаскивая карточку на другую, — они поменяются местами.', 'En Hoy caben 4 tarjetas. Cambia el orden arrastrando una tarjeta sobre otra — intercambian su lugar.', 'Auf Heute passen 4 Karten. Die Reihenfolge änderst du, indem du eine Karte auf eine andere ziehst — sie tauschen die Plätze.', 'La page Aujourd’hui a de la place pour 4 cartes. Pour changer l’ordre, fais glisser une carte sur une autre — elles échangent leur place.', 'Cabem 4 cartões em Hoje. Para mudar a ordem, arraste um cartão sobre outro — eles trocam de lugar.')
_tr7('metric.over.more', '心拍が高心拍の上限を超えていた時間。この上限は設定するものではありません — 私があなたのセッションから算出し、少しずつ微調整します（「{page}」ページの「時計と心拍」カードで確認できます）。成績ではありません — 短いピークはゲームにつきものです。意味があるのは、同じくらいのプレイ時間なのに、数字が夜ごとに増えていくときです — そのときは、その夜に何が変わったのかを振り返ってみてください。', '你的心率在高心率上限以上待了多久。这个上限不用你设置——我根据你的记录计算，并慢慢微调（可以在“{page}”页面的“手表与心率”卡片里看到）。这不是评分——短暂的峰值本来就是游戏的一部分。值得留意的是，在游戏时长相同的情况下，这个数字一晚比一晚高——那时可以看看那几个晚上有什么变化。', 'Сколько времени твой пульс провёл выше границы высокого пульса. Её ты не настраиваешь — я вычисляю её по твоим сессиям и понемногу уточняю (она видна на странице «{page}», в карточке «Часы и пульс»). Это не оценка: короткие пики — часть игры. Интересно становится, когда число растёт вечер за вечером при одинаково долгой игре, — тогда попробуй посмотреть, что в эти вечера изменилось.', 'Cuánto tiempo pasó tu pulso por encima del límite de pulso alto. Ese límite no lo ajustas tú — lo calculo a partir de tus sesiones y lo voy afinando poco a poco (lo ves en la página «{page}», en la tarjeta «Reloj y pulso»). No es una nota — los picos breves forman parte del juego. Lo interesante es cuando el número crece noche tras noche con el mismo tiempo de juego — entonces fíjate en qué cambió esas noches.', 'Wie lange dein Puls über deiner Grenze für hohen Puls lag. Die stellst du nicht ein — ich berechne sie aus deinen Sitzungen und stimme sie langsam fein ab (du siehst sie auf der Seite „{page}“ in der Karte „Uhr und Puls“). Das ist keine Note — kurze Spitzen gehören zum Spielen. Interessant wird es, wenn die Zahl Abend für Abend bei gleich langem Spielen wächst — dann schau, was sich an diesen Abenden verändert hat.', 'Combien de temps ton pouls a passé au-dessus de ta limite de pouls élevé. Tu ne la règles pas — je la calcule à partir de tes séances et je l’affine lentement (tu la vois sur la page « {page} », dans la carte « Montre et pouls »). Ce n’est pas une note — les pics courts font partie du jeu. Ça devient intéressant quand le chiffre augmente soir après soir pour une même durée de jeu — regarde alors ce qui a changé ces soirs-là.', 'Quanto tempo o seu pulso passou acima do seu limite de pulso alto. Você não o define — eu o calculo a partir das suas sessões e o ajusto aos poucos (você o vê na página “{page}”, no cartão “Relógio e pulso”). Não é uma nota — picos curtos fazem parte do jogo. Fica interessante quando o número cresce noite após noite com o mesmo tempo de jogo — aí vale olhar o que mudou nessas noites.')
_tr7('metric.breath.title', '合図', '提示', 'Подсказки', 'Avisos', 'Hinweise', 'Rappels', 'Avisos')
_tr7('metric.breath.short', 'このセッションで、負荷がしばらく高いまま続いたときに私が自分から出した合図の数。', '本次记录中，在你的负荷持续偏高一阵子时，我主动给你的提示次数。', 'Сколько подсказок я сама дала тебе в этой сессии — когда нагрузка какое-то время держалась высокой.', 'Cuántos avisos te di por mi cuenta en esta sesión, cuando tu carga se mantuvo alta un rato.', 'Wie viele Hinweise ich dir in dieser Sitzung von selbst gegeben habe — wenn deine Last eine Weile oben blieb.', 'Combien de rappels je t’ai donnés de moi-même pendant cette séance — quand ta charge est restée haute un moment.', 'Quantos avisos eu te dei sozinha nesta sessão — quando a sua carga ficou alta por um tempo.')
_tr7('metric.breath.more', '合図は4つのうちのひとつ — 重心、顎、手と視線、呼吸 — で、オンにしたものを順番に使います。数えるのは、負荷がしばらく高いまま続いたときに私が自分から出したものだけで、あなたが「テスト」ボタンで試したものは含みません。音なしで画像だけだった合図も数えます。', '提示是四种之一——重心、下颌、手与视线或呼吸——我会在你打开的那些之间轮换。只统计我在你负荷持续偏高一阵子时主动给出的提示；你用“测试”按钮的尝试不算。只显示图片、没有声音的提示也算在内。', 'Подсказка — одна из четырёх: опора, челюсть, рука и взгляд или дыхание, — и я чередую те, что у тебя включены. Считаются только те, что я дала сама, когда нагрузка какое-то время держалась высокой; твои пробы кнопкой «Тест» не считаются. Подсказки, пришедшие только картинкой, без звука, тоже считаются.', 'Un aviso es uno de cuatro (centro, mandíbula, mano y mirada o respiración) y voy alternando los que tienes activados. Solo cuentan los que di por mi cuenta, cuando tu carga se mantuvo alta un rato; tus pruebas con el botón «Probar» no cuentan. También cuentan los avisos que llegaron solo como imagen, sin sonido.', 'Ein Hinweis ist einer von vier — Erdung, Kiefer, Hand und Blick oder Atem — und ich wechsle zwischen denen, die du eingeschaltet hast. Es zählen nur die, die ich von selbst gegeben habe, als deine Last eine Weile oben blieb; deine eigenen Versuche mit dem „Testen“-Knopf nicht. Hinweise, die nur als Bild ohne Ton kamen, zählen auch.', 'Un rappel est l’un des quatre — ancrage, mâchoire, main et regard ou respiration — et j’alterne ceux que tu as activés. Ne comptent que ceux que j’ai donnés de moi-même, quand ta charge est restée haute un moment ; tes essais avec le bouton « Tester » ne comptent pas. Les rappels venus seulement en image, sans son, comptent aussi.', 'Um aviso é um de quatro — centro, mandíbula, mão e olhar ou respiração — e eu alterno entre os que você deixou ligados. Só contam os que eu dei sozinha, quando a sua carga ficou alta por um tempo; os seus testes com o botão “Testar” não contam. Avisos que vieram só como imagem, sem som, também contam.')
_tr7('metric.week.more', '週は月曜日から数え、今いるワールド（ゲームまたは仕事）のセッションだけを数えます。今週私がどれだけ記録したかを見渡すためだけのものです。', '一周从周一算起，只统计你当前所在世界（游戏或工作）的记录。它只是让你大致了解我本周记录了多少。', 'Неделя считается с понедельника, и учитываются только сессии мира, в котором ты сейчас (Игра или Работа). Это просто обзор того, сколько я записала за эту неделю.', 'La semana se cuenta desde el lunes y solo cuentan las sesiones del mundo en el que estás ahora (Juego o Trabajo). Sirve solo para ver cuánto he registrado esta semana.', 'Die Woche zählt ab Montag, und es zählen nur Sitzungen der Welt, in der du gerade bist (Spiel oder Arbeit). Sie dient nur als Überblick, wie viel ich diese Woche aufgezeichnet habe.', 'La semaine commence le lundi, et seules comptent les séances du monde où tu te trouves (Jeu ou Travail). C’est juste un aperçu de ce que j’ai enregistré cette semaine.', 'A semana conta a partir de segunda-feira, e só entram as sessões do mundo em que você está agora (Jogo ou Trabalho). Serve só como visão geral de quanto eu registrei esta semana.')
_tr7('metric.session_len.title', 'セッションの長さ', '记录时长', 'Длина сессии', 'Duración de la sesión', 'Sitzungslänge', 'Durée de la séance', 'Duração da sessão')
_tr7('metric.session_len.short', 'セッションの長さ — 見守りを始めてからの時間。', '本次记录持续了多久——从我开始关注算起。', 'Сколько длится сессия — с тех пор, как я начала наблюдение.', 'Cuánto dura la sesión: desde que empecé a observar.', 'Wie lange die Sitzung läuft — seit ich mit der Beobachtung begonnen habe.', 'La durée de la séance — depuis que j’ai commencé à observer.', 'Quanto tempo a sessão dura — desde que comecei a observar.')
_tr7('metric.session_len.more', 'セッションはゲームを起動したときではなく、私が見守りを始めたときに始まり、見守りを止めたときに終わります。ただの時計で評価ではありません：長いセッションが悪いわけでも、短いセッションが良いわけでもありません。今見守っていないときは、カードに「—」と表示されます。', '记录从我开始关注时算起，而不是从你启动游戏时算起，在你停止关注时结束。这只是一个时钟，不是评分：长记录不代表不好，短记录也不代表好。我现在没有在关注时，卡片显示“—”。', 'Сессия начинается, когда я начинаю наблюдение, а не когда ты запускаешь игру, и заканчивается, когда ты останавливаешь наблюдение. Это просто часы, а не оценка: длинная сессия — не плохо, короткая — не хорошо. Когда я сейчас не наблюдаю, карточка показывает «—».', 'La sesión empieza cuando empiezo a observar, no cuando abres el juego, y termina cuando detienes la observación. Es solo un reloj, no una nota: una sesión larga no es mala y una corta no es buena. Cuando ahora mismo no observo, la tarjeta muestra «—».', 'Eine Sitzung beginnt, wenn ich mit der Beobachtung anfange, nicht wenn du das Spiel startest, und endet, wenn du die Beobachtung stoppst. Es ist nur eine Uhr, keine Bewertung: Eine lange Sitzung ist nicht schlecht und eine kurze nicht gut. Wenn ich gerade nicht beobachte, zeigt die Karte „—“.', 'Une séance commence quand je commence à observer, pas quand tu lances le jeu, et se termine quand tu arrêtes l’observation. Ce n’est qu’une horloge, pas une note : une longue séance n’est pas mauvaise et une courte n’est pas bonne. Quand je n’observe pas en ce moment, la carte affiche « — ».', 'A sessão começa quando começo a observar, não quando você abre o jogo, e termina quando você para a observação. É só um relógio, não uma nota: sessão longa não é ruim e sessão curta não é boa. Quando não estou observando agora, o cartão mostra “—”.')
_tr7('metric.last_cue.title', '最後の合図から', '距上次提示', 'С последней подсказки', 'Desde el último aviso', 'Seit dem letzten Hinweis', 'Depuis le dernier rappel', 'Desde o último aviso')
_tr7('metric.last_cue.more', '数えるのは、私が自分から出し、実際に表示された合図だけです — 「テスト」ボタンで試したものは含みません。このセッションでまだ一度も来ていなければ、カードに「—」が表示されます。これは目標でも連続記録でもありません。長い沈黙はうまくいっているという意味ではなく、合図はあなたが何か間違っているという意味でもありません。私が最後に声をかけたのがいつか、それだけです。', '只统计我主动发出、并且确实显示出来的提示——你用“测试”按钮试的不算。本次记录中还没有提示时，卡片显示“—”。这不是目标，也不是连胜：长时间的安静不代表你状态好，出现提示也不代表你做错了什么。它只是我上一次出声的时间。', 'Считается только подсказка, которую я подала сама и которая действительно показалась, — твои пробы кнопкой «Тест» не засчитываются. Пока в этой сессии не пришло ни одной, карточка показывает «—». Это не цель и не серия: долгая тишина не значит, что у тебя всё получается, а подсказка не значит, что ты делаешь что-то не так. Это просто момент, когда я подала голос в последний раз.', 'Solo cuenta un aviso que di por mí misma y que de verdad se mostró — tus pruebas con el botón «Probar» no cuentan. Mientras no haya llegado ninguno en esta sesión, la tarjeta muestra «—». No es una meta ni una racha: un silencio largo no significa que lo estés haciendo bien, y un aviso no significa que estés haciendo algo mal. Es solo cuándo avisé por última vez.', 'Gezählt wird nur ein Hinweis, den ich von selbst gegeben habe und der wirklich angezeigt wurde — deine eigenen Versuche mit dem Knopf „Testen“ zählen nicht. Solange in dieser Sitzung keiner kam, zeigt die Karte „—“. Das ist weder ein Ziel noch eine Serie: Lange Stille heißt nicht, dass es bei dir gut läuft, und ein Hinweis heißt nicht, dass du etwas falsch machst. Es ist nur, wann ich mich zuletzt gemeldet habe.', 'Ne compte qu’un rappel que j’ai envoyé de moi-même et qui s’est réellement affiché — tes essais avec le bouton « Tester » ne comptent pas. Tant qu’aucun n’est arrivé pendant cette séance, la carte affiche « — ». Ce n’est ni un objectif ni une série : un long silence ne veut pas dire que tu t’en sors bien, et un rappel ne veut pas dire que tu fais quelque chose de travers. C’est juste le moment où je me suis manifestée pour la dernière fois.', 'Só conta um aviso que eu dei por conta própria e que apareceu de fato — os seus testes com o botão “Testar” não contam. Enquanto nenhum chegar nesta sessão, o cartão mostra “—”. Não é meta nem sequência: um silêncio longo não quer dizer que você está indo bem, e um aviso não quer dizer que você está fazendo algo errado. É só quando eu avisei pela última vez.')
_tr7('metric.calm_time.title', '平静の時間', '平静时间', 'Время в покое', 'Tiempo en calma', 'Zeit in Ruhe', 'Temps au calme', 'Tempo em calma')
_tr7('metric.calm_time.short', 'セッションのうち、心拍が平静の帯にあった分数。', '本次记录中你的心率在平静区间里待了多少分钟。', 'Сколько минут сессии твой пульс был в зоне покоя.', 'Cuántos minutos de la sesión estuvo tu pulso en la zona de calma.', 'Wie viele Minuten der Sitzung dein Puls in der Ruhezone war.', 'Combien de minutes de la séance ton pouls est resté dans la zone calme.', 'Quantos minutos da sessão o seu pulso passou na zona de calma.')
_tr7('metric.calm_time.more', '平静は「セッションの内訳」パネルと同じ帯です。安静時からの上昇が 10 BPM 未満の心拍のこと。これは心拍の話であって、あなたがどれだけ穏やかに感じたかではありません。スコアではありません — 分数が多いほど良い夜というわけではなく、緊迫した試合で心拍が上がるのは当然のことです。最初の夜、私がまだあなたの安静時の値を知らない間は、カードに「—」が表示されます。', '这里的平静和“这次都在哪个区间”面板里是同一个区间：心率比你的平静水平高不到 10 BPM。它说的是心率，而不是你感觉自己有多平静。这不是分数——分钟数多不代表这个晚上更好；紧张的比赛会让心率升高，本来就该如此。第一个晚上，在我还不了解你的平静水平时，卡片会显示“—”。', 'Покой — та же зона, что и на панели «Где прошла сессия»: пульс меньше чем на 10 BPM выше твоего покоя. Это о пульсе, а не о твоём ощущении спокойствия. Это не очки — больше минут не значит лучший вечер; напряжённый матч поднимает пульс, и так и должно быть. В первый вечер, пока я ещё не знаю твой покой, карточка показывает «—».', 'La calma es la misma zona que en el panel «Dónde fue la sesión»: pulso a menos de 10 BPM por encima de tu reposo. Habla del pulso, no de tu sensación de calma. No es una puntuación — más minutos no significan una noche mejor; una partida tensa sube el pulso, y así debe ser. En tu primera noche, mientras aún no conozco tu reposo, la tarjeta muestra «—».', 'Ruhe ist dieselbe Zone wie im Panel „Wo die Sitzung lag“: ein Puls weniger als 10 BPM über deiner Ruhe. Sie sagt etwas über den Puls, nicht darüber, wie ruhig du dich gefühlt hast. Das ist kein Score — mehr Minuten bedeuten keinen besseren Abend; ein angespanntes Match hebt den Puls, und so soll es sein. Am ersten Abend, solange ich deine Ruhe noch nicht kenne, zeigt die Karte „—“.', 'Le calme, c’est la même zone que dans le panneau « Où la séance s’est passée » : un pouls à moins de 10 BPM au-dessus de ton niveau de repos. Ça parle de ton pouls, pas de ton sentiment de calme. Ce n’est pas un score — plus de minutes ne veut pas dire une meilleure soirée ; un match tendu fait monter le pouls, et c’est bien ainsi. Le premier soir, tant que je ne connais pas encore ton niveau de repos, la carte affiche « — ».', 'A calma é a mesma zona do painel “Onde a sessão passou”: pulso menos de 10 BPM acima do seu repouso. Fala do pulso, não da sua sensação de calma. Não é pontuação — mais minutos não significam uma noite melhor; uma partida tensa sobe o pulso, e é assim que deve ser. Na primeira noite, enquanto eu ainda não conheço o seu repouso, o cartão mostra “—”.')
_tr7('metric.signal.title', '信号の品質', '信号质量', 'Качество сигнала', 'Calidad de la señal', 'Signalqualität', 'Qualité du signal', 'Qualidade do sinal')
_tr7('metric.signal.short', 'あなたの心拍をどれだけ受け取れているか：セッションのうち、実際に心拍が届いていた割合。', '我接收你心率的情况：本次记录中有多大比例的时间心率真正传了过来。', 'Насколько хорошо я принимаю твой пульс: какую часть сессии он действительно приходил.', 'Lo bien que recibo tu pulso: durante qué parte de la sesión llegó de verdad.', 'Wie gut ich deinen Puls empfange: in welchem Anteil der Sitzung er wirklich ankam.', 'À quel point je reçois bien ton pouls : pendant quelle part de la séance il est vraiment arrivé.', 'Quão bem eu recebo o seu pulso: em que parte da sessão ele realmente chegou.')
_tr7('metric.signal.more', 'パーセントは、最初のサンプル以降の時間のうち、実際に心拍が届いていた時間の割合です。カードの「·」のあとの数字は、このセッションで心拍が途切れた回数です — 一度も途切れていなければ表示されません。パーセントは1分たってからカードに表示されます。それより早いと、一度の途切れが接続不良のように見えてしまうからです。これは時計 → 電話 → Wi‑Fi → PC という経路の話で、あなたの心臓やあなた自身の話ではありません。低いときは、合図が減ることがあります。数えている途中で心拍が途切れると、私は数え直すからです。「履歴」では、心拍が届き始めるまでの待ち時間も含めたセッション全体で計算するため、短いセッションはそこで低めに出ます。', '百分比是从第一个样本起，心率真正传过来的时间所占的比例。卡片上“·”后面的数字是本次记录中心率中断的次数——一次都没有时就不显示。卡片要满一分钟后才显示百分比，太早的话，一个小空档就会看起来像连接很差。它反映的是 手表 → 手机 → Wi‑Fi → 电脑 这条链路，而不是你的心脏，也不是你本人。数值低时，提示可能会变少：如果心率在计时中途中断，我会从头开始计时。在“历史”里，它按整次记录计算，包括等待心率开始传来的时间，所以短的记录在那里数值会偏低。', 'Процент — это время, когда пульс действительно приходил, от времени с первого замера. Число после «·» на карточке — сколько раз в этой сессии пульс пропадал; если ни разу, его там нет. Процент появляется на карточке только через минуту — раньше один пропуск выглядел бы как плохое соединение. Это о пути часы → телефон → Wi‑Fi → компьютер, а не о твоём сердце и не о тебе. Когда он низкий, подсказок может быть меньше: если пульс пропадает посреди подсчёта, я начинаю считать заново. В «Истории» он считается по всей сессии, включая ожидание, пока не начал приходить пульс, поэтому короткие сессии там выходят ниже.', 'El porcentaje es el tiempo en que el pulso llegó de verdad, respecto al tiempo desde la primera muestra. El número tras «·» en la tarjeta es cuántas veces se cortó el pulso en esta sesión — si no se cortó ninguna, no aparece. El porcentaje aparece en la tarjeta solo pasado un minuto; antes, un solo hueco parecería una mala conexión. Habla del camino reloj → móvil → Wi‑Fi → PC, no de tu corazón ni de ti. Cuando es bajo, puede haber menos avisos: si el pulso se corta a mitad del conteo, empiezo a contar de nuevo. En el Historial se calcula sobre toda la sesión, incluida la espera hasta que empezó a llegar el pulso, por eso ahí las sesiones cortas salen más bajas.', 'Der Prozentwert ist die Zeit, in der der Puls wirklich ankam, bezogen auf die Zeit seit dem ersten Messwert. Die Zahl hinter „·“ auf der Karte gibt an, wie oft der Puls in dieser Sitzung ausgefallen ist — wenn nie, steht sie nicht da. Der Prozentwert erscheint auf der Karte erst nach einer Minute; früher würde eine einzige Lücke wie eine schlechte Verbindung aussehen. Er sagt etwas über den Weg Uhr → Handy → WLAN → PC, nicht über dein Herz oder über dich. Ist er niedrig, kann es weniger Hinweise geben: Wenn der Puls mitten im Zählen ausfällt, beginne ich von vorn zu zählen. Im Verlauf wird er über die ganze Sitzung berechnet, einschließlich des Wartens, bis der Puls zum ersten Mal ankam, deshalb fallen kurze Sitzungen dort niedriger aus.', 'Le pourcentage est le temps où le pouls est vraiment arrivé, rapporté au temps écoulé depuis le premier échantillon. Le chiffre après « · » sur la carte indique combien de fois le pouls a décroché pendant cette séance — s’il n’a jamais décroché, il n’apparaît pas. La carte n’affiche le pourcentage qu’au bout d’une minute ; plus tôt, un seul trou ressemblerait à une mauvaise connexion. Ça parle du trajet montre → téléphone → Wi‑Fi → ordinateur, pas de ton cœur ni de toi. Quand il est bas, il peut y avoir moins de rappels : si le pouls décroche au milieu du comptage, je recommence à compter. Dans l’Historique, il est calculé sur toute la séance, y compris l’attente avant l’arrivée du premier pouls ; c’est pourquoi les séances courtes y sortent plus bas.', 'A porcentagem é o tempo em que o pulso realmente chegou, em relação ao tempo desde a primeira amostra. O número depois do “·” no cartão é quantas vezes o sinal do pulso caiu nesta sessão — se não caiu nenhuma vez, ele não aparece. A porcentagem só aparece no cartão depois de um minuto; antes disso, uma única falha pareceria uma conexão ruim. Fala do caminho relógio → celular → Wi‑Fi → PC, não do seu coração nem de você. Quando está baixa, pode haver menos avisos: se o sinal do pulso cai no meio da contagem, começo a contar de novo. No Histórico, é calculada sobre a sessão inteira, incluindo a espera até o pulso começar a chegar, por isso lá as sessões curtas saem mais baixas.')
_tr7('metric.felt_vs_measured.title', '感覚と計測', '感受与测量', 'Ощущаемое и измеренное', 'Sentido y medido', 'Gefühlt und gemessen', 'Ressenti et mesuré', 'Sentido e medido')
_tr7('metric.felt_vs_measured.short', 'アンケートで答えた「感じた負荷」と、計測した負荷のピークを並べたもの。どちらも 0–10。', '你在问卷里填写的主观强度，与测得的负荷峰值并排显示，两者都是 0–10。', 'Твоя ощущаемая нагрузка из опроса рядом с измеренным пиком нагрузки, оба числа 0–10.', 'Tu carga percibida en el cuestionario junto al pico de carga medido, ambos de 0–10.', 'Deine empfundene Last aus dem Fragebogen neben der gemessenen Last-Spitze, beide 0–10.', 'Ta charge ressentie, d’après le questionnaire, à côté du pic de charge mesuré, les deux sur 0–10.', 'A sua carga percebida no questionário ao lado do pico de carga medido, ambos de 0–10.')
_tr7('metric.felt_vs_measured.more', '「今日」のカードは、このワールド（ゲームまたは仕事）で最後に終わったセッションを、「履歴」の詳細は選んだセッションを使います。1つ目の数字は、セッション後のアンケートであなたが評価した負荷です。2つ目は、同じセッションの最高負荷（0–100 のピーク）を10で割ったものです。一致しなくてもかまいませんし、どちらも「正解」ではありません — 心拍はあなたがどう感じたかを見られず、あなたは一拍一拍を感じられません。両者の差は誤りではなく、情報です。アンケートを飛ばした場合は「—」が表示されます。', '“今天”页面上的卡片取这个世界（游戏或工作）最近一次已结束的记录，“历史”里的详情则取你选中的那一次。第一个数字是你在记录结束后的问卷里给负荷打的分。第二个是同一次记录的最高负荷（0–100 的峰值）除以十。两者不一定一致，也没有哪个才是“正确的”——心率看不到你当时的感受，你也感觉不到每一次心跳。两者之间的差距不是错误，而是信息。如果你跳过了问卷，就显示“—”。', 'Карточка на «Сегодня» берёт последнюю завершённую сессию этого мира (Игра или Работа), подробности в «Истории» — выбранную. Первое число — твоя оценка нагрузки в опросе после сессии. Второе — самая высокая нагрузка той же сессии (пик 0–100), делённая на десять. Они не обязаны совпадать, и ни одно из них не «правильное» — пульс не видит, как тебе было, а ты не чувствуешь каждый удар. Разница между ними — не ошибка, а информация. Если опрос пропущен, будет «—».', 'La tarjeta de Hoy toma la última sesión terminada de este mundo (Juego o Trabajo); el detalle en el Historial, la que elegiste. El primer número es cómo valoraste la carga en el cuestionario tras la sesión. El segundo es la carga más alta de esa misma sesión (el pico de 0–100) dividida entre diez. No tienen por qué coincidir y ninguno es «el correcto» — el pulso no ve cómo te sentías, y tú no sientes cada latido. La diferencia entre ellos no es un error, es información. Si te saltaste el cuestionario, muestra «—».', 'Die Karte auf Heute nimmt die letzte beendete Sitzung dieser Welt (Spiel oder Arbeit), das Detail im Verlauf die, die du ausgewählt hast. Die erste Zahl ist, wie du die Last im Fragebogen nach der Sitzung bewertet hast. Die zweite ist die höchste Last derselben Sitzung (Spitze 0–100) geteilt durch zehn. Sie müssen nicht übereinstimmen, und keine ist „die richtige“ — der Puls sieht nicht, wie es dir ging, und du spürst nicht jeden Schlag. Der Unterschied zwischen ihnen ist kein Fehler, sondern eine Information. Wenn du den Fragebogen übersprungen hast, zeigt sie „—“.', 'La carte de la page Aujourd’hui prend la dernière séance terminée de ce monde (Jeu ou Travail), le détail dans l’Historique prend celle que tu as choisie. Le premier chiffre est la note que tu as donnée à la charge dans le questionnaire après la séance. Le second est la charge la plus haute de cette même séance (pic 0–100) divisée par dix. Ils ne doivent pas forcément correspondre, et aucun n’est « le bon » — le pouls ne voit pas comment tu te sentais, et tu ne sens pas chaque battement. L’écart entre eux n’est pas une erreur, c’est une information. Si tu as sauté le questionnaire, la carte affiche « — ».', 'O cartão em Hoje usa a última sessão encerrada deste mundo (Jogo ou Trabalho); o detalhe no Histórico usa a que você escolheu. O primeiro número é como você avaliou a carga no questionário depois da sessão. O segundo é a carga mais alta dessa mesma sessão (o pico de 0–100) dividida por dez. Eles não precisam bater, e nenhum dos dois é “o certo” — o pulso não vê como você se sentiu, e você não sente cada batida. A diferença entre eles não é um erro, é informação. Se você pulou o questionário, aparece “—”.')
_tr7('dashboard.unit.session_len', 'セッション開始から', '自本次记录开始', 'с начала сессии', 'desde el inicio de la sesión', 'seit Sitzungsbeginn', 'depuis le début de la séance', 'desde o início da sessão')
_tr7('dashboard.unit.last_cue', '最後の合図から', '距上次提示', 'с последней подсказки', 'desde el último aviso', 'seit dem letzten Hinweis', 'depuis le dernier rappel', 'desde o último aviso')
_tr7('dashboard.unit.calm_time', 'このセッションの平静', '本次处于平静', 'в покое за сессию', 'en calma esta sesión', 'in Ruhe in dieser Sitzung', 'au calme pendant la séance', 'em calma nesta sessão')
_tr7('dashboard.unit.signal', '心拍が届いた時間', '有心率的时间', 'времени с пульсом', 'del tiempo con pulso', 'der Zeit mit Puls', 'du temps avec pouls', 'do tempo com pulso')
_tr7('dashboard.unit.felt_vs_measured', '感覚 · 計測、0–10', '感受 · 测量，0–10', 'ощущаемое · измеренное, 0–10', 'sentido · medido, 0–10', 'gefühlt · gemessen, 0–10', 'ressenti · mesuré, 0–10', 'sentido · medido, 0–10')
_tr7('dashboard.fmt.min', '{n} 分', '{n} 分钟', '{n} мин', '{n} min', '{n} min', '{n} min', '{n} min')
_tr7('dashboard.fmt.h_min', '{h} 時間 {m} 分', '{h} 小时 {m} 分', '{h} ч {m} мин', '{h} h {m} min', '{h} h {m} min', '{h} h {m} min', '{h} h {m} min')
_tr7('dashboard.fmt.pct', '{n}%', '{n}%', '{n} %', '{n} %', '{n} %', '{n} %', '{n}%')
_tr7('insight.cue_dropouts', '最近のセッションでは、数えている最中に心拍が1セッションあたり平均 {n} 回途切れ、そのたびに数え直しになりました — そのため合図が少なくなることがあります。心拍は時計から電話へ Bluetooth で、電話から PC へ Wi‑Fi で届きます — 時計は電話のそばに、電話は Wi‑Fi ルーターの近くに置いてください。PC から離れるときは、電話を持っていってください。', '在最近的记录里，你的心率平均每次有 {n} 次恰好在计时过程中中断，每次计时都得从头开始——所以提示可能会变少。心率从手表通过蓝牙传到手机，再从手机通过 Wi‑Fi 传到电脑——让手表靠近手机，手机靠近 Wi‑Fi 路由器。离开电脑时，把手机带在身边。', 'В последних сессиях пульс у тебя пропадал в среднем {n}× за сессию как раз во время подсчёта, и подсчёт каждый раз начинался заново — поэтому подсказок может быть меньше. Пульс идёт с часов на телефон по Bluetooth, а с телефона по Wi‑Fi на компьютер — держи часы рядом с телефоном, а телефон поближе к Wi‑Fi роутеру. Когда отходишь от компьютера, бери телефон с собой.', 'En tus últimas sesiones, el pulso se te cortó de media {n}× por sesión justo durante el conteo, y cada vez el conteo empezó de nuevo, por eso puede haber menos avisos. El pulso va del reloj al móvil por Bluetooth y del móvil al PC por Wi‑Fi: ten el reloj cerca del móvil y el móvil cerca del router Wi‑Fi. Cuando te alejes del PC, llévate el móvil.', 'Dein Puls ist in den letzten Sitzungen im Schnitt {n}× pro Sitzung genau während des Zählens ausgefallen, und das Zählen begann jedes Mal von vorn — deshalb kann es weniger Hinweise geben. Der Puls geht von der Uhr per Bluetooth zum Handy und vom Handy über WLAN zum PC — halte die Uhr beim Handy und das Handy nah am WLAN-Router. Wenn du vom PC weggehst, nimm das Handy mit.', 'Lors de tes dernières séances, ton pouls a décroché en moyenne {n}× par séance pile pendant le comptage, et le comptage a chaque fois recommencé à zéro — c’est pourquoi il peut y avoir moins de rappels. Le pouls passe de la montre au téléphone par Bluetooth, et du téléphone à l’ordinateur par Wi‑Fi — garde la montre près du téléphone et le téléphone près du routeur Wi‑Fi. Quand tu t’éloignes de l’ordinateur, emporte le téléphone avec toi.', 'Nas suas últimas sessões, o sinal do pulso caiu em média {n}× por sessão justamente durante a contagem, e a contagem recomeçou do zero toda vez — por isso pode haver menos avisos. O pulso vai do relógio para o celular por Bluetooth, e do celular para o PC por Wi‑Fi — mantenha o relógio perto do celular e o celular perto do roteador Wi‑Fi. Quando sair de perto do PC, leve o celular junto.')
_tr7('insight.cue_never_above', '直近 {n} 回のセッションで、負荷は一度もしきい値を超えませんでした — 合図を出す理由がありませんでした。しきい値は設定ではありません：あなたのセッションから算出し、あなたを知るにつれて動かします。現在の値は「設定」→「合図」で見られます。', '在最近 {n} 次记录里，你的负荷一次都没有超过阈值——我没有理由提醒你。阈值不是一项设置：我根据你的记录计算它，并随着对你的了解逐步调整。当前的阈值可以在“设置 → 提示”里看到。', 'В последних сессиях ({n}) нагрузка ни разу не поднималась выше порога — мне не было повода подать знак. Порог — не настройка: я вычисляю его по твоим сессиям и сдвигаю по мере того, как узнаю тебя. Текущий видно в «Настройки → Подсказки».', 'En tus últimas {n} sesiones la carga no superó el umbral ni una vez, así que no tenía por qué avisar. El umbral no es un ajuste: lo calculo a partir de tus sesiones y lo voy moviendo a medida que te conozco. El actual lo ves en Ajustes → Avisos.', 'In deinen letzten {n} Sitzungen ist die Last kein einziges Mal über die Schwelle gekommen — ich hatte keinen Grund, mich zu melden. Die Schwelle ist keine Einstellung: Ich berechne sie aus deinen Sitzungen und verschiebe sie, während ich dich kennenlerne. Die aktuelle siehst du unter Einstellungen → Hinweise.', 'Lors de tes {n} dernières séances, la charge n’a pas une seule fois dépassé le seuil — je n’avais aucune raison de me manifester. Le seuil n’est pas un réglage : je le calcule à partir de tes séances et je le déplace à mesure que je te connais. Tu vois l’actuel dans Paramètres → Rappels.', 'Nas suas últimas {n} sessões a carga não passou do limiar nem uma vez — eu não tinha motivo para avisar. O limiar não é uma configuração: eu o calculo a partir das suas sessões e o ajusto conforme vou te conhecendo. O atual está em Configurações → Avisos.')
_tr7('insight.cue_almost', '負荷は上がりましたが、連続で最長 {sec} 秒 — {need} 秒には届きませんでした。惜しいところでした。私は、短いピークのたびに声をかけないよう、負荷が高いまま続くのをわざと待っています。', '负荷确实升高过，但最长只连续了 {sec} 秒——离 {need} 秒还差一点。差得不多。我会刻意等负荷在高位保持住，以免每个短暂的峰值都出声。', 'Нагрузка поднималась, но дольше всего {sec} с подряд — до {need} с не хватило. Было близко. Я намеренно жду, пока нагрузка продержится наверху, чтобы не подавать голос при каждом коротком пике.', 'La carga sí subió, pero lo más largo fueron {sec} s seguidos — faltaba llegar a {need} s. Estuvo cerca. Espero a propósito a que la carga se mantenga alta, para no avisar con cada pico breve.', 'Die Last war oben, aber höchstens {sec} s am Stück — bis {need} s hat es nicht gereicht. Es war knapp. Ich warte absichtlich, bis die Last oben bleibt, damit ich mich nicht bei jeder kurzen Spitze melde.', 'La charge est bien montée, mais au plus long {sec} s d’affilée — il en fallait {need}. C’était juste. J’attends exprès que la charge tienne, pour ne pas me manifester à chaque pic bref.', 'A carga ficou alta, mas por no máximo {sec} s seguidos — não deu para chegar a {need} s. Foi por pouco. Espero de propósito que a carga se mantenha alta, para não avisar a cada pico curto.')
_tr7('insight.cue_far', '負荷はしきい値を超えましたが、ほんの短い間でした — 必要な {need} 秒のうち、最長で {sec} 秒。あなたの体は、私が待つよりも速く上がり下がりします。短いピークではわざと合図を出しません — ここで設定することはありません。', '你的负荷确实超过了阈值，但只是一下子——最长 {sec} 秒，而我需要 {need} 秒。你的身体起落得比我等待的更快。对短暂的峰值我故意不出声——这里没有什么需要设置的。', 'Нагрузка поднималась выше порога, но лишь ненадолго — самое большее {sec} с из нужных {need} с. Твоё тело поднимается и опускается быстрее, чем я жду. На короткие пики я нарочно не реагирую — настраивать тут нечего.', 'La carga sí superó el umbral, pero solo un momento: como mucho {sec} s de los {need} s que necesito. Tu cuerpo sube y baja más rápido de lo que yo espero. En los picos cortos no aviso a propósito: aquí no hay nada que ajustar.', 'Die Last ist über die Schwelle gekommen, aber nur kurz — höchstens {sec} s von den nötigen {need} s. Dein Körper geht schneller rauf und runter, als ich warte. Bei kurzen Spitzen melde ich mich absichtlich nicht — hier gibt es nichts einzustellen.', 'La charge a bien dépassé le seuil, mais brièvement — au plus {sec} s sur les {need} s nécessaires. Ton corps monte et redescend plus vite que je n’attends. Sur les pics courts, je ne me manifeste pas exprès — il n’y a rien à régler ici.', 'A carga passou do limiar, mas só por um instante — no máximo {sec} s dos {need} s necessários. O seu corpo sobe e desce mais rápido do que eu espero. Em picos curtos eu não aviso de propósito — não há nada para ajustar aqui.')
_tr7('insight.resting_up', '最近のセッションでは、安静時ベースラインが以前より {delta} BPM 高くなっています — 睡眠不足、カフェイン、それとも風邪？ 必ずしもゲームのせいではありません。', '最近几次记录的静息基线比之前高 {delta} BPM——也许是睡得少、咖啡因或者感冒了？不一定是游戏造成的。', 'Базовая линия покоя в последних сессиях на {delta} BPM выше, чем в предыдущих, — может, меньше сна, кофеин или простуда? Не обязательно из-за игр.', 'Tu línea base en reposo está {delta} BPM más alta en las últimas sesiones que en las anteriores — ¿quizá menos sueño, cafeína o un resfriado? No viene necesariamente del juego.', 'Deine Ruhebasislinie liegt in den letzten Sitzungen {delta} BPM höher als in den Sitzungen davor — vielleicht weniger Schlaf, Koffein oder eine Erkältung? Das kommt nicht unbedingt vom Spielen.', 'Sur les dernières séances, ta ligne de base au repos est plus haute de {delta} BPM que sur les précédentes — peut-être moins de sommeil, de la caféine ou un rhume ? Ce n’est pas forcément dû au jeu.', 'A sua linha de base em repouso está {delta} BPM mais alta nas últimas sessões do que nas anteriores — talvez menos sono, cafeína ou um resfriado? Não é necessariamente por causa do jogo.')
_tr7('insight.resting_down', '最近のセッションでは、安静時ベースラインが以前より {delta} BPM 低くなっています。睡眠がよくなった、カフェインが減った、あるいは単に計測中に穏やかな時間が多かっただけかもしれません — 数字ひとつでは見分けられません。', '最近几次记录的静息基线比之前低 {delta} BPM。可能是睡得更好、咖啡因更少，也可能只是测量时恰好比较平静——单凭一个数字分辨不出来。', 'Базовая линия покоя в последних сессиях на {delta} BPM ниже, чем в предыдущих. Это может быть лучший сон, меньше кофеина или просто более спокойные моменты во время измерения — одно число этого не различит.', 'Tu línea base en reposo está {delta} BPM más baja en las últimas sesiones que en las anteriores. Puede ser mejor sueño, menos cafeína o solo momentos más tranquilos al medir — un solo número no lo distingue.', 'Deine Ruhebasislinie liegt in den letzten Sitzungen {delta} BPM niedriger als in den Sitzungen davor. Das kann besserer Schlaf sein, weniger Koffein oder einfach ruhigere Momente beim Messen — eine einzelne Zahl kann das nicht unterscheiden.', 'Sur les dernières séances, ta ligne de base au repos est plus basse de {delta} BPM que sur les précédentes. Ça peut être un meilleur sommeil, moins de caféine ou simplement des moments plus calmes pendant la mesure — un seul chiffre ne permet pas de trancher.', 'A sua linha de base em repouso está {delta} BPM mais baixa nas últimas sessões do que nas anteriores. Pode ser sono melhor, menos cafeína ou só momentos mais calmos durante a medição — um único número não consegue distinguir.')
_tr7('insight.hrr_up', '最近のセッションでは、心拍回復が以前より {delta} BPM 速くなっています。いい兆しです — ただ、数回のセッションからでは確かなことは言えず、あくまで手がかりです。', '最近几次记录的心率恢复比之前快 {delta} BPM。是个不错的信号——但只凭几次记录，这更像是一个迹象，而不是定论。', 'Восстановление пульса в последних сессиях на {delta} BPM быстрее, чем раньше. Хороший сигнал — но по нескольким сессиям это скорее намёк, чем уверенность.', 'La recuperación del pulso es {delta} BPM más rápida en las últimas sesiones que antes. Buena señal — pero con pocas sesiones es más un indicio que una certeza.', 'Die Herzfrequenz-Erholung ist in den letzten Sitzungen {delta} BPM schneller als vorher. Ein schönes Signal — aber aus ein paar Sitzungen ist das eher ein Anzeichen als eine Gewissheit.', 'Sur les dernières séances, ta récupération cardiaque est plus rapide de {delta} BPM qu’avant. Joli signe — mais sur quelques séances, c’est plutôt un indice qu’une certitude.', 'A recuperação do pulso está {delta} BPM mais rápida nas últimas sessões do que antes. Um bom sinal — mas, com poucas sessões, é mais um indício do que uma certeza.')
_tr7('insight.hrr_down', '最近のセッションでは、心拍回復が以前より {delta} BPM 遅くなっています。数回のセッションからでは、あくまで手がかりです — 心拍がどれだけ高く跳ねたかにもよりますし、睡眠、疲れ、あるいはゲームの種類の違いが関係しているかもしれません。', '最近几次记录的心率恢复比之前慢 {delta} BPM。只凭几次记录，这更像是一个迹象——它也取决于心率冲得有多高，背后可能是睡眠、疲劳或者玩的游戏类型不同。', 'Восстановление пульса в последних сессиях на {delta} BPM медленнее, чем раньше. По нескольким сессиям это скорее намёк — зависит и от того, насколько высоко подскочил пульс, а за этим могут стоять сон, усталость или другой тип игр.', 'La recuperación del pulso es {delta} BPM más lenta en las últimas sesiones que antes. Con pocas sesiones es más un indicio que una certeza — también depende de lo alto que se disparó el pulso, y puede deberse al sueño, al cansancio o a otro tipo de juegos.', 'Die Herzfrequenz-Erholung ist in den letzten Sitzungen {delta} BPM langsamer als vorher. Aus ein paar Sitzungen ist das eher ein Anzeichen — es hängt auch davon ab, wie hoch der Puls gesprungen ist, und dahinter können Schlaf, Müdigkeit oder eine andere Art von Spielen stecken.', 'Sur les dernières séances, ta récupération cardiaque est plus lente de {delta} BPM qu’avant. Sur quelques séances, c’est plutôt un indice — ça dépend aussi de la hauteur à laquelle ton pouls est monté, et le sommeil, la fatigue ou un autre type de jeu peuvent y être pour quelque chose.', 'A recuperação do pulso está {delta} BPM mais lenta nas últimas sessões do que antes. Com poucas sessões, é mais um indício — depende também de quão alto o pulso subiu, e pode ter a ver com sono, cansaço ou outro tipo de jogo.')
_tr7('insight.triggers_early', '1.5 時間以上のセッションでは、合図の {share}% が最初の1時間に来ました。これが続くなら、セッションの始まりそのものがあなたを高ぶらせているのかもしれません — もっと穏やかな始め方を試して、変わるかどうか見てみてください。', '在 1.5 小时及以上的记录中，{share}% 的提示出现在第一个小时。如果反复如此，也许正是开局让你紧绷起来——试试更平缓的热身，看看情况是否改变。', 'В сессиях от 1,5 ч {share} % подсказок пришлись на первый час. Если это повторяется, возможно, тебя разгоняет именно начало — попробуй более спокойный разгон и посмотри, изменится ли что-то.', 'En las sesiones de 1,5 h o más, el {share} % de los avisos llegó en la primera hora. Si se repite, quizá lo que te acelera sea justo el comienzo — prueba un arranque más tranquilo y observa si cambia.', 'In Sitzungen ab 1,5 h kamen {share} % der Hinweise in der ersten Stunde. Wenn sich das wiederholt, bringt dich vielleicht gerade der Anfang auf Touren — probier einen ruhigeren Einstieg und beobachte, ob sich das ändert.', 'Dans les séances de 1,5 h et plus, {share} % des rappels sont arrivés dans la première heure. Si ça se répète, c’est peut-être justement le début qui te fait monter en régime — essaie un démarrage plus tranquille et regarde si ça change.', 'Nas sessões de 1,5 h ou mais, {share}% dos avisos vieram na primeira hora. Se isso se repetir, talvez seja justamente o começo que te acelera — tente um início mais tranquilo e veja se muda.')
_tr7('insight.triggers_late', '2.5 時間以上のセッションでは、合図の {share}% が2時間を過ぎてから来ました — 長いセッションは緊張を長引かせるのかもしれません。休憩を挟んだ短めのセッションを試してみてください。', '在 2.5 小时及以上的记录中，{share}% 的提示在两小时之后才出现——长时间连续玩可能让你一直处于紧绷状态；试试玩得短一些，中间休息一下。', 'В сессиях от 2,5 ч {share} % подсказок пришли только после двух часов — долгие сессии могут держать тебя в напряжении; попробуй сессии покороче с перерывом.', 'En las sesiones de 2,5 h o más, el {share} % de los avisos llegó después de dos horas — las sesiones largas pueden mantenerte en tensión; prueba sesiones más cortas con una pausa.', 'In Sitzungen ab 2,5 h kamen {share} % der Hinweise erst nach zwei Stunden — lange Sitzungen können dich unter Spannung halten; probier kürzere Sitzungen mit einer Pause.', 'Dans les séances de 2,5 h et plus, {share} % des rappels sont arrivés après deux heures — les longues séances peuvent te maintenir sous tension ; essaie des séances plus courtes avec une pause.', 'Nas sessões de 2,5 h ou mais, {share}% dos avisos vieram só depois de duas horas — sessões longas podem te manter em tensão; tente sessões mais curtas, com pausa.')
_tr7('insight.over_up', '最近のセッションでは、以前よりもセッションの大きな割合を上限超えで過ごしています（平均 {minutes} 分）。ゲームのせいかもしれませんし、睡眠やカフェインのせいかもしれません — あるいは単に、私がセッションのたびにあなたのデータから上限を微調整しているだけかもしれません。この状態が続くなら、「ガイド」の呼吸法を試してみるのもいいでしょう。', '最近几次记录中，你在上限以上的时间占比比之前更大（平均 {minutes} 分钟）。可能是游戏的原因，也可能是睡眠或咖啡因——或者只是因为我在每次记录后都会根据你的数据微调上限。如果一直这样，可以试试“指南”里的呼吸方法。', 'В последних сессиях пульс был выше границы дольше, чем раньше (в среднем {minutes} мин). Причиной может быть игра, но и сон или кофеин — или просто то, что я после каждой сессии уточняю границу по твоим данным. Если так и останется, можешь попробовать дыхание из «Справочника».', 'En las últimas sesiones pasaste por encima del límite una parte mayor de la sesión que antes (media {minutes} min). Puede deberse al juego, pero también al sueño o a la cafeína — o simplemente a que afino el límite tras cada sesión según tus datos. Si sigue así, puedes probar la respiración de la Guía.', 'In den letzten Sitzungen hast du einen größeren Teil der Sitzung über der Grenze verbracht als vorher (Schnitt {minutes} Min). Dahinter kann das Spiel stecken, aber auch Schlaf oder Koffein — oder einfach, dass ich die Grenze nach jeder Sitzung anhand deiner Daten nachjustiere. Wenn es so bleibt, kannst du die Atmung aus dem Leitfaden ausprobieren.', 'Sur les dernières séances, ton pouls est resté au-dessus de la limite pendant une plus grande part de la séance qu’avant (moyenne {minutes} min). Ça peut venir du jeu, mais aussi du sommeil ou de la caféine — ou simplement du fait que j’affine la limite après chaque séance d’après tes données. Si ça reste ainsi, tu peux essayer la respiration du Guide.', 'Nas últimas sessões, você passou uma parte maior da sessão acima do limite do que antes (média de {minutes} min). Pode ser o jogo, mas também o sono ou a cafeína — ou só o fato de eu ajustar o limite depois de cada sessão com base nos seus dados. Se continuar assim, você pode experimentar a respiração do Guia.')
_tr7('insight.steady', '{n} 回のセッションで、私はまだ何も気づいていません。', '在 {n} 次记录中，我暂时没有发现什么。', 'Я пока ничего не заметила (сессий: {n}).', 'En {n} sesiones todavía no he notado nada.', 'In {n} Sitzungen ist mir bisher nichts aufgefallen.', 'Sur {n} séances, je n’ai encore rien remarqué.', 'Em {n} sessões, ainda não notei nada.')
_tr7('guide.philosophy.source12', '息を吐くと心拍は自然に遅くなる（Lehrer & Gevirtz, 2014）', '呼气时心率会自然放慢（Lehrer & Gevirtz，2014）', 'на выдохе пульс естественным образом замедляется (Lehrer & Gevirtz, 2014)', 'al exhalar, el pulso se ralentiza de forma natural (Lehrer & Gevirtz, 2014)', 'beim Ausatmen wird der Puls von Natur aus langsamer (Lehrer & Gevirtz, 2014)', 'à l’expiration, le pouls ralentit naturellement (Lehrer & Gevirtz, 2014)', 'ao expirar, o coração desacelera naturalmente (Lehrer & Gevirtz, 2014)')
_tr7('guide.philosophy.source11', 'ゆっくりした呼吸は、より穏やかな状態と結びついている（Zaccaro ら, 2018）', '缓慢呼吸与更平静的状态相关（Zaccaro 等，2018）', 'медленное дыхание связано с более спокойным состоянием (Zaccaro и др., 2018)', 'la respiración lenta se asocia con un estado más tranquilo (Zaccaro et al., 2018)', 'langsames Atmen geht mit einem ruhigeren Zustand einher (Zaccaro u. a., 2018)', 'une respiration lente va de pair avec un état plus calme (Zaccaro et al., 2018)', 'a respiração lenta está associada a um estado mais calmo (Zaccaro et al., 2018)')
_tr7('guide.philosophy.source10', '競技的なプレイは、心臓に本物のストレス反応を引き起こす（Ketelhut & Nigg, 2024）', '竞技游戏会引发心脏真实的应激反应（Ketelhut & Nigg，2024）', 'соревновательная игра запускает настоящую стрессовую реакцию сердца (Ketelhut & Nigg, 2024)', 'el juego competitivo desencadena una respuesta de estrés real en el corazón (Ketelhut & Nigg, 2024)', 'kompetitives Spielen löst eine echte Stressreaktion des Herzens aus (Ketelhut & Nigg, 2024)', 'le jeu compétitif déclenche une véritable réaction de stress du cœur (Ketelhut & Nigg, 2024)', 'o jogo competitivo desencadeia uma resposta real de estresse no coração (Ketelhut & Nigg, 2024)')
_tr7('ob.step3.body2', 'アプリはすべてのセッションを覚えています。数週間たつと、緊張したあとどれだけ速く落ち着くかなど、あなたの傾向を見せます — 時計からのおおまかな目安で、診断ではありません。', '应用会记住每一次记录。几周后，它会给你看你的趋势，比如紧张之后你多快平静下来——来自手表的粗略参考，不是诊断。', 'Приложение запоминает каждую сессию. Через несколько недель оно покажет твои тенденции — например, как быстро ты успокаиваешься после напряжения. Это ориентир по данным часов, а не диагноз.', 'La app recuerda cada sesión. Tras unas semanas te muestra tus tendencias, como lo rápido que te calmas después de un momento de tensión: una orientación del reloj, no un diagnóstico.', 'Die App merkt sich jede Sitzung. Nach ein paar Wochen zeigt sie dir deine Trends, etwa wie schnell du nach Anspannung zur Ruhe kommst — ein grober Anhaltspunkt von der Uhr, keine Diagnose.', 'L’app garde chaque séance en mémoire. Après quelques semaines, elle te montre tes tendances, comme la vitesse à laquelle tu te calmes après un moment intense — une indication de la montre, pas un diagnostic.', 'O app lembra de cada sessão. Depois de algumas semanas, mostra as suas tendências, como a rapidez com que você se acalma depois de um momento tenso — uma referência do relógio, não um diagnóstico.')
_tr7('history.minutes', '{m} 分', '{m} 分钟', '{m} мин', '{m} min', '{m} min', '{m} min', '{m} min')
_tr7('dock.snooze_active_tip', '今はいい — {until} まで声をかけません', '现在不要——{until} 之前我不会出声', 'Не сейчас — до {until} не подам голос', 'Ahora no — hasta las {until} no aviso', 'Jetzt nicht — bis {until} melde ich mich nicht', 'Pas maintenant — je ne me manifeste pas avant {until}', 'Agora não — até {until} não vou avisar')
_tr7('dnes.empty_body', '時計をつなぐと、ここに心拍と負荷を描きます — そして負荷がしばらく高いまま続くと、自分から合図を出します。', '连接手表后，我会在这里画出你的心率和负荷——当你的负荷持续偏高一阵子时，我会主动给你一条提示。', 'Когда подключишь часы, я буду рисовать здесь пульс и нагрузку — а когда нагрузка какое-то время держится высокой, сама подам подсказку.', 'Cuando vincules el reloj, dibujaré aquí tu pulso y tu carga, y cuando la carga se mantenga alta un rato, te avisaré por mi cuenta.', 'Sobald du die Uhr verbindest, zeichne ich hier Puls und Last — und wenn deine Last eine Weile oben bleibt, melde ich mich von selbst mit einem Hinweis.', 'Quand tu connectes ta montre, je dessine ici ton pouls et ta charge — et quand ta charge reste haute un moment, je me manifeste toute seule avec un rappel.', 'Quando você parear o relógio, vou desenhar aqui o seu pulso e a sua carga — e, quando a carga ficar alta por um tempo, aviso sozinha.')
_tr7('settings.auto_profile_sub', '知っているゲーム：{games}。数秒ごとに、動いているプログラムの名前だけを見ます。ゲームを見つけたらそのプロファイルに切り替えて開始し、閉じたら停止します（自分で開始した場合）。オフ = プログラム名は読みません。', '我认识的游戏：{games}。每隔几秒，我只看正在运行的程序名称。找到游戏后，我会切换到它的配置文件并启动；你关闭它时，我会停止（如果是我自己启动的）。关闭 = 我不读取程序名称。', 'Игры, которые я знаю: {games}. Каждые несколько секунд я смотрю только на названия запущенных программ. Найдя игру, переключаюсь на её профиль и запускаюсь; когда закроешь её, останавливаюсь (если запустилась сама). Выключено = названия программ не читаю.', 'Juegos que conozco: {games}. Cada pocos segundos miro solo los nombres de los programas abiertos. Cuando encuentro un juego, cambio a su perfil y me inicio; cuando lo cierras, me detengo (si me inicié sola). Desactivado = no leo los nombres de los programas.', 'Spiele, die ich kenne: {games}. Alle paar Sekunden schaue ich nur auf die Namen laufender Programme. Finde ich ein Spiel, wechsle ich zu seinem Profil und starte; schließt du es, stoppe ich (wenn ich von selbst gestartet bin). Aus = ich lese keine Programmnamen.', 'Jeux que je connais : {games}. Toutes les quelques secondes, je regarde seulement les noms des programmes ouverts. Quand je trouve un jeu, je passe à son profil et je me lance ; quand tu le fermes, je m’arrête (si je m’étais lancée toute seule). Désactivé = je ne lis pas les noms des programmes.', 'Jogos que eu conheço: {games}. A cada poucos segundos olho só os nomes dos programas abertos. Quando encontro um jogo, troco para o perfil dele e começo; quando você o fecha, paro (se eu comecei sozinha). Desligado = não leio os nomes dos programas.')
_tr7('guide.block.science', '役立つかもしれない理由', '为什么可能有帮助', 'Почему это может помочь', 'Por qué puede ayudar', 'Warum es helfen kann', 'Pourquoi ça peut aider', 'Por que pode ajudar')
_tr7('hr.ip_show', 'IP を表示', '显示 IP', 'Показать IP', 'Mostrar IP', 'IP zeigen', 'Afficher l’IP', 'Mostrar IP')
_tr7('hr.ip_hide', 'IP を隠す', '隐藏 IP', 'Скрыть IP', 'Ocultar IP', 'IP verbergen', 'Masquer l’IP', 'Ocultar IP')
_tr7('hr.ip_hidden_note', '配信やスクリーンショットに映らないよう、アドレスは隠しています。電話に入力するときは「IP を表示」をクリックしてください。', '我把地址隐藏起来，免得它出现在直播或截图里。点击“显示 IP”后，再把它抄到手机里。', 'Адрес я скрываю, чтобы его не было видно на стриме или скриншоте. В телефон его перепишешь, нажав «Показать IP».', 'Oculto la dirección para que no se vea en el stream ni en una captura de pantalla. Para escribirla en el móvil, pulsa «Mostrar IP».', 'Die Adresse verberge ich, damit sie weder im Stream noch auf einem Screenshot zu sehen ist. Ins Handy überträgst du sie nach einem Klick auf „IP zeigen“.', 'Je masque l’adresse pour qu’on ne la voie ni sur un stream ni sur une capture d’écran. Pour la recopier dans le téléphone, clique sur « Afficher l’IP ».', 'Escondo o endereço para que ele não apareça na stream nem em screenshots. Para digitá-lo no celular, clique em “Mostrar IP”.')
_tr7('hr.pair_status_waiting', '● 電話がつながるのを待っています…', '● 正在等待手机连接…', '● Жду, пока подключится телефон…', '● Esperando a que se conecte el móvil…', '● Ich warte, bis sich das Handy verbindet…', '● J’attends que le téléphone se connecte…', '● Esperando o celular se conectar…')
_tr7('hr.pair_status_no_client', '● 電話はまだつながっていません。確認することは下にあります。', '● 手机还没有连上。要检查的内容在下面。', '● Телефон пока не подключился. Что проверить — ниже.', '● El móvil aún no se ha conectado. Qué revisar, más abajo.', '● Das Handy hat sich noch nicht verbunden. Was du prüfen kannst, steht unten.', '● Le téléphone ne s’est pas encore connecté. Ce qu’il faut vérifier est plus bas.', '● O celular ainda não se conectou. O que verificar está mais abaixo.')
_tr7('hr.pair_status_linked', '● 電話がつながりました — 心拍を待っています…', '● 手机已连接——正在等待心率…', '● Телефон подключён — жду пульс…', '● Móvil conectado: esperando el pulso…', '● Handy verbunden — ich warte auf den Puls…', '● Téléphone connecté — j’attends le pouls…', '● Celular conectado — esperando o pulso…')
_tr7('hr.pair_status_ok', '✓ 心拍が届いています：{bpm} BPM。このウィンドウは閉じて大丈夫。', '✓ 心率已传过来：{bpm} BPM。可以关闭这个窗口了。', '✓ Пульс идёт: {bpm} BPM. Окно можно закрыть.', '✓ El pulso llega: {bpm} BPM. Ya puedes cerrar la ventana.', '✓ Der Puls kommt an: {bpm} BPM. Du kannst das Fenster schließen.', '✓ Le pouls arrive : {bpm} BPM. Tu peux fermer la fenêtre.', '✓ O pulso está chegando: {bpm} BPM. Pode fechar a janela.')
_tr7('hr.pair_status_busy', '● ポート {port} は別のプログラムが使用中 — もう一度試しています…', '● 端口 {port} 被其他程序占用——正在重试…', '● Порт {port} занят другой программой — пробую снова…', '● Otro programa tiene el puerto {port}: lo intento de nuevo…', '● Ein anderes Programm belegt Port {port} — ich versuche es erneut…', '● Un autre programme occupe le port {port} — je réessaie…', '● Outro programa está usando a porta {port} — tentando de novo…')
_tr7('hr.pair_status_gave_up', '✕ ポート {port} は別のプログラムが使用中。「{page}」ページで変更し、電話にも同じ番号を入れて。', '✕ 端口 {port} 被其他程序占用。请在“{page}”页面修改它，并在手机里填同一个号码。', '✕ Порт {port} занят другой программой. Поменяй его на странице «{page}» и введи то же число в телефоне.', '✕ Otro programa tiene el puerto {port}. Cámbialo en la página «{page}» y pon el mismo número en el móvil.', '✕ Ein anderes Programm belegt Port {port}. Ändere ihn auf der Seite „{page}“ und trag dieselbe Zahl im Handy ein.', '✕ Un autre programme occupe le port {port}. Change-le sur la page « {page} » et saisis le même numéro sur le téléphone.', '✕ Outro programa está usando a porta {port}. Mude-a na página “{page}” e digite o mesmo número no celular.')
_tr7('hr.pair_status_off', '✕ 心拍の受信が始まりませんでした。このウィンドウを閉じて、もう一度開いて — もう一度試します。', '✕ 心率接收没有启动。关闭这个窗口再打开——我会再试一次。', '✕ Приём пульса не включился. Закрой это окно и открой снова — я попробую ещё раз.', '✕ La recepción del pulso no arrancó. Cierra esta ventana y ábrela otra vez: lo intentaré de nuevo.', '✕ Der Pulsempfang ist nicht angesprungen. Schließ dieses Fenster und öffne es neu — ich versuche es noch einmal.', '✕ La réception du pouls n’a pas démarré. Ferme cette fenêtre et rouvre-la — je réessaierai.', '✕ O recebimento do pulso não começou. Feche esta janela e abra de novo — vou tentar outra vez.')
_tr7('hud.trigger_row.sub', '心拍パネルの下に、4つの合図のアイコンを表示します。見るためだけのもので、ゲーム中の画像の代わりにはなりません — 合図には少なくとも1つの画像をオンにしておく必要があります。', '在心率面板下方显示你四条提示的图标。它们只是给你看的，不能代替游戏中的图片——提示至少需要打开其中一张图片。', 'Под панелью пульса появятся значки четырёх твоих подсказок. Они только для вида и не заменяют картинки в игре — подсказке нужна хотя бы одна включённая картинка.', 'Bajo el panel de pulso aparecen los iconos de tus cuatro avisos. Son solo para verlos y no sustituyen a las imágenes en el juego: un aviso necesita al menos una de ellas activada.', 'Unter dem Puls-Panel erscheinen die Symbole deiner vier Hinweise. Sie sind nur zum Anschauen und ersetzen die Bilder im Spiel nicht — ein Hinweis braucht mindestens eines davon eingeschaltet.', 'Sous le panneau du pouls s’affichent les icônes de tes quatre rappels. Elles sont là pour la vue et ne remplacent pas les images en jeu — un rappel a besoin d’au moins une d’elles activée.', 'Abaixo do painel de pulso aparecem os ícones dos seus quatro avisos. São só para ver e não substituem as imagens no jogo — um aviso precisa de pelo menos uma delas ligada.')
_tr7('log.hotkey_failed', 'ショートカット {combo} は別のアプリが使っているため、「今はいい」は使えません。私を黙らせるには、上のバーで停止してください — ただしそうすると、計測も止まります。', '快捷键 {combo} 被其他应用占用了，所以“现在不要”用不了。你仍然可以在顶部横条里停止我来让我安静——不过那样我也会停止测量。', 'Сочетание {combo} занято другим приложением, так что «не сейчас» не сработает. Заставить меня замолчать можно остановкой в полосе вверху — но тогда я перестану и измерять.', 'Otra aplicación está usando el atajo {combo}, así que «ahora no» no funcionará. Puedes silenciarme deteniéndome en la barra de arriba — pero entonces también dejo de medir.', 'Das Tastenkürzel {combo} ist von einer anderen Anwendung belegt, deshalb steht „Jetzt nicht“ nicht zur Verfügung. Stumm schalten kannst du mich, indem du mich in der Leiste oben stoppst — dann höre ich aber auch auf zu messen.', 'Une autre application occupe le raccourci {combo}, donc « pas maintenant » ne marchera pas. Tu peux me faire taire en m’arrêtant dans la barre en haut — mais alors j’arrête aussi de mesurer.', 'Outro aplicativo está usando o atalho {combo}, então o “agora não” não vai funcionar. Para me silenciar, você pode me parar na barra lá em cima — mas aí eu paro de medir também.')
_tr7('log.snooze_started', '今はいい：{minutes} 分間は合図を出しません。見守りは止まりません。', '现在不要：{minutes} 分钟内我不会出声。这不会停止关注。', 'Не сейчас: {minutes} минут я молчу. Наблюдение это не останавливает.', 'Ahora no: no aviso durante {minutes} minutos. Esto no detiene la observación.', 'Jetzt nicht: {minutes} Minuten melde ich mich nicht. Die Beobachtung stoppt das nicht.', 'Pas maintenant : je ne me manifeste pas pendant {minutes} minutes. Ça n’arrête pas l’observation.', 'Agora não: não aviso por {minutes} minutos. Isso não para a observação.')
_tr7('dnes.trace_meta', '{time} · 合図 {n} 回', '{time} · 提示 {n} 次', '{time} · подсказки {n}×', '{time} · avisos {n}×', '{time} · Hinweise {n}×', '{time} · rappels {n}×', '{time} · avisos {n}×')
_tr7('log.edge_not_cached_later', 'この合図の自然な音声はまだ準備できていません — 今回は Windows の音声で話します。見守り中は準備しません。見守りを止めたら準備します。', '这条提示的自然语音还没准备好——这次我用 Windows 语音说。关注期间我不准备它；你停止关注后我再准备。', 'Естественный голос для этой подсказки ещё не готов — в этот раз говорю голосом Windows. Во время наблюдения я его не готовлю; подготовлю, когда ты остановишь наблюдение.', 'La voz natural de este aviso aún no está lista: esta vez hablo con la voz de Windows. No la preparo mientras observo; lo haré cuando detengas la observación.', 'Die natürliche Stimme für diesen Hinweis ist noch nicht fertig — diesmal spreche ich mit der Windows-Stimme. Während der Beobachtung bereite ich sie nicht vor; das mache ich, wenn du die Beobachtung stoppst.', 'La voix naturelle de ce rappel n’est pas encore prête — cette fois, je parle avec la voix Windows. Je ne la prépare pas pendant l’observation ; je le ferai quand tu l’arrêteras.', 'A voz natural deste aviso ainda não está pronta — desta vez falo com a voz do Windows. Não preparo durante a observação; faço isso quando você parar de observar.')
_tr7('settings.audio_reset_sub', '音量、バランス、話す速さが、アプリの初期値に戻ります。選んだ音声はそのままです。', '音量、比例和语速都会恢复为应用自带的默认值。已选的语音保持不变。', 'Громкость, баланс и скорость речи вернутся к значениям, с которыми приложение поставлялось. Выбранный голос останется.', 'El volumen, la mezcla y la velocidad del habla vuelven a los valores con los que venía la app. La voz elegida se mantiene.', 'Lautstärke, Verhältnis und Sprechtempo gehen auf die Werte zurück, mit denen die App ausgeliefert wurde. Die gewählte Stimme bleibt.', 'Le volume, l’équilibre et la vitesse de parole reviennent aux valeurs d’origine de l’app. La voix choisie reste.', 'O volume, a mistura e a velocidade da fala voltam aos valores de fábrica do app. A voz escolhida continua.')
_tr7('history.export_local', '私は心拍もセッションもどこにも送りません — このコンピューターの中だけにあり、ファイルは好きな場所に保存できます。', '我不会把你的心率和记录发送到任何地方——它们只在你的电脑里，文件保存在哪儿由你决定。', 'Пульс и сессии я никуда не отправляю — они только на твоём компьютере, а файл ты сохранишь, куда захочешь.', 'No envío tu pulso ni tus sesiones a ninguna parte — están solo en tu ordenador, y el archivo lo guardas donde quieras.', 'Puls und Sitzungen schicke ich nirgendwohin — sie sind nur auf deinem Rechner, und die Datei speicherst du, wo du willst.', 'Je n’envoie ton pouls et tes séances nulle part — ils restent seulement sur ton ordinateur, et tu enregistres le fichier où tu veux.', 'Não envio o seu pulso nem as suas sessões para lugar nenhum — eles ficam só no seu computador, e você salva o arquivo onde quiser.')
_tr7('history.export_col.breathing', 'アプリからの合図', '应用发出的提示', 'Подсказки от приложения', 'Avisos de la app', 'Hinweise der App', 'Rappels de l’app', 'Avisos do app')
_tr7('history.export_col.signal', '信号 %', '信号 %', 'сигнал %', 'señal %', 'Signal %', 'signal %', 'sinal %')
_tr7('history.export_col.world', 'ワールド', '世界', 'мир', 'mundo', 'Welt', 'monde', 'mundo')
_tr7('history.export_col.dropouts', '心拍の途切れ', '心率中断', 'пропадания пульса', 'cortes de pulso', 'Puls-Ausfälle', 'coupures du pouls', 'quedas de sinal do pulso')
_tr7('history.export_col.blind_s', '信号なし (秒)', '无信号 (秒)', 'без сигнала (с)', 'sin señal (s)', 'ohne Signal (s)', 'sans signal (s)', 'sem sinal (s)')
_tr7('history.export_col.pause_episodes', '入力の休み', '输入停顿', 'паузы во вводе', 'pausas en la entrada', 'Eingabepausen', 'pauses dans les entrées', 'pausas na entrada')
_tr7('tour.sensor.body', 'ここで電話からあなたの心拍を受け取ります。心拍があれば、負荷がしばらく高いまま続いたときに自分から合図を出します — ゲームの最中にあなたが思い出す必要はありません。時計がなければ黙っています。', '我在这里接收手机发来的心率。有了心率，当你的负荷持续偏高一阵子时，我会主动提醒你——你不用在激烈的游戏中自己想起来。没有手表，我就保持安静。', 'Здесь я принимаю твой пульс с телефона. Когда он есть, я сама подаю знак, если нагрузка какое-то время держится высокой, — тебе не нужно помнить об этом в разгар игры. Без часов я молчу.', 'Aquí recibo tu pulso desde el móvil. Cuando lo tengo, te aviso por mi cuenta cuando la carga se mantiene alta un rato: no tienes que acordarte tú en plena partida. Sin reloj, me callo.', 'Hier empfange ich deinen Puls vom Handy. Sobald ich ihn habe, melde ich mich von selbst, wenn deine Last eine Weile oben bleibt — du musst mitten im Spiel nicht selbst daran denken. Ohne Uhr schweige ich.', 'C’est ici que je reçois ton pouls depuis le téléphone. Quand je l’ai, je me manifeste toute seule quand ta charge reste haute un moment — tu n’as pas à y penser en pleine partie. Sans montre, je me tais.', 'É aqui que recebo o seu pulso do celular. Quando tenho o pulso, aviso sozinha quando a sua carga fica alta por um tempo — você não precisa lembrar disso no meio do jogo. Sem relógio, fico calada.')
_tr7('hr.qr_ios', 'iPhone / Apple Watch\n「PulseOSC」（有料）。\nまだ試されていません。\nアドレスとポートは「時計のつなぎ方…」にある。', 'iPhone / Apple Watch\n“PulseOSC”（付费）。\n尚未测试。\n地址和端口在“如何连接手表…”里。', 'iPhone / Apple Watch\n«PulseOSC» (платно).\nПока не проверено.\nАдрес и порт — в «Как подключить часы…».', 'iPhone / Apple Watch\n«PulseOSC» (de pago).\nAún no probado.\nLa dirección y el puerto están en «Cómo vincular tu reloj…».', 'iPhone / Apple Watch\n„PulseOSC“ (kostenpflichtig).\nNoch nicht ausprobiert.\nAdresse und Port findest du unter „Uhr verbinden…“.', 'iPhone / Apple Watch\n« PulseOSC » (payant).\nPas encore testé.\nL’adresse et le port sont dans « Comment connecter ta montre… ».', 'iPhone / Apple Watch\n“PulseOSC” (pago).\nAinda não testado.\nO endereço e a porta estão em “Como parear o seu relógio…”.')
_tr7('hr.qr_addr_above', 'アドレスとポートは上の枠にある。', '地址和端口在上方的框里。', 'Адрес и порт — в рамке выше.', 'La dirección y el puerto están en el recuadro de arriba.', 'Adresse und Port findest du im Feld oben.', 'L’adresse et le port sont dans le cadre ci-dessus.', 'O endereço e a porta estão no quadro acima.')
_tr7('ob.step1.how', '何かを押したり覚えたりする必要はありません — アプリがあなたの負荷を見て、負荷がもう上がっていない合間に自分から声をかけます。心拍が「ピーク」の帯にある間は、あえて黙っています。', '你不需要按任何东西，也不需要记住任何事——应用会关注你的负荷，在负荷不再上升的间歇里主动出声。你的心率处于高峰区间时，它宁可保持安静。', 'Тебе не нужно ничего нажимать или запоминать — приложение следит за твоей нагрузкой и само подаёт голос в паузе, когда нагрузка уже не растёт. Пока твой пульс в пиковой зоне, оно лучше промолчит.', 'No tienes que pulsar ni recordar nada — la app vigila tu carga y avisa por sí sola en una pausa, cuando la carga ya no sube. Mientras tu pulso está en la zona de pico, prefiere guardar silencio.', 'Du musst nichts drücken und dir nichts merken — die App verfolgt deine Last und meldet sich von selbst in einer Pause, wenn die Last nicht mehr steigt. Solange dein Puls im Spitzenbereich ist, schweigt sie lieber.', 'Tu n’as aucun bouton à presser ni rien à retenir — l’app surveille ta charge et se manifeste d’elle-même pendant une pause, quand la charge ne monte plus. Tant que ton pouls est en zone de pic, elle préfère se taire.', 'Você não precisa apertar nada nem lembrar de nada — o app acompanha a sua carga e avisa por conta própria numa pausa, quando a carga já não está subindo. Enquanto o seu pulso está na zona de pico, ele prefere ficar em silêncio.')
_tr7('history.unit.session_len', '1セッションあたりの分数', '每次记录的分钟数', 'минут на сессию', 'minutos por sesión', 'Minuten pro Sitzung', 'minutes par séance', 'minutos por sessão')
_tr7('history.unit.calm_time', '1セッションあたりの分数', '每次记录的分钟数', 'минут на сессию', 'minutos por sesión', 'Minuten pro Sitzung', 'minutes par séance', 'minutos por sessão')
_tr7('history.unit.signal', '心拍が届いた時間の %', '有心率的时间 %', '% времени с пульсом', '% del tiempo con pulso', '% der Zeit mit Puls', '% du temps avec pouls', '% do tempo com pulso')
_tr7('history.unit.breath', '1セッションあたりの平均', '每次记录的平均值', 'в среднем на сессию', 'media por sesión', 'Schnitt pro Sitzung', 'moyenne par séance', 'média por sessão')
_tr7('history.effect_title', '合図のあと心拍がどう動いたか', '提示之后心率如何变化', 'Как менялся пульс после подсказки', 'Cómo se movió el pulso tras un aviso', 'Wie sich der Puls nach einem Hinweis bewegte', 'Comment le pouls a bougé après un rappel', 'Como o pulso se moveu depois de um aviso')
_tr7('history.effect_hint', '鳴った合図のあとの心拍の変化（ゲームのみ）。中央より左は心拍が下がったことを意味します — ただ、心拍は自然にも下がりますし、合図は今、負荷がもう上がっていないときにしか来ないので、合図のあとに下がっても効いた証拠にはなりません。細い線は、本当の値がありそうな範囲です — それが中央をまたいでいる間は、差が逆向きの可能性もあります。', '出声的提示之后心率的变化（仅限游戏）。在中线左侧表示心率下降了——但心率本身也会下降，而且现在提示只在负荷不再上升时才出现，所以提示后的下降并不能证明它起了作用。细线是真实数值很可能所在的范围——只要它跨过中线，差异也可能是反方向的。', 'Сдвиг пульса после прозвучавшей подсказки (только игра). Левее центра — пульс снизился, но пульс снижается и сам, а подсказка теперь приходит, только когда нагрузка уже не растёт, так что снижение после неё — не доказательство, что она сработала. Тонкая черта — диапазон, в котором, вероятно, находится настоящее значение: пока она заходит за центр, разница может быть и обратной.', 'Cambio del pulso tras un aviso que sonó (solo juego). A la izquierda del centro significa que el pulso bajó — pero el pulso también baja solo, y ahora el aviso llega solo cuando la carga ya no sube, así que una bajada después de él no prueba que haya funcionado. La línea fina es el rango en el que probablemente está el valor real — mientras cruce el centro, la diferencia también podría ser la contraria.', 'Veränderung des Pulses nach einem Hinweis, der erklungen ist (nur Spiel). Links von der Mitte heißt, dass der Puls gesunken ist — aber der Puls sinkt auch von selbst, und der Hinweis kommt jetzt erst, wenn die Last nicht mehr steigt; ein Abfall danach ist also kein Beweis, dass er gewirkt hat. Der dünne Strich ist der Bereich, in dem der wahre Wert wahrscheinlich liegt — solange er über die Mitte reicht, kann der Unterschied auch umgekehrt sein.', 'Variation du pouls après un rappel qui a retenti (Jeu seulement). À gauche du centre, ça veut dire que le pouls a baissé — mais le pouls baisse aussi tout seul, et le rappel n’arrive maintenant que quand la charge ne monte plus, donc une baisse après lui ne prouve pas qu’il a fait effet. Le trait fin est la plage où se trouve probablement la vraie valeur — tant qu’il traverse le centre, l’écart peut aussi aller dans l’autre sens.', 'A variação do pulso depois de um aviso que tocou (só Jogo). À esquerda do centro significa que o pulso caiu — mas o pulso também cai sozinho, e agora o aviso só vem quando a carga já não está subindo, então uma queda depois dele não prova que funcionou. A linha fina é a faixa em que o valor real provavelmente está — enquanto ela cruza o centro, a diferença pode ser até o contrário.')
_tr7('history.detail_breath', '合図', '提示', 'Подсказки', 'Avisos', 'Hinweise', 'Rappels', 'Avisos')
_tr7('history.detail_calm', '平静', '平静', 'В покое', 'En calma', 'In Ruhe', 'Au calme', 'Em calma')
_tr7('history.detail_signal', '信号', '信号', 'Сигнал', 'Señal', 'Signal', 'Signal', 'Sinal')
_tr7('history.detail_felt', '感覚 · 計測', '感受 · 测量', 'Ощущаемое · измеренное', 'Sentido · medido', 'Gefühlt · gemessen', 'Ressenti · mesuré', 'Sentido · medido')
_tr7('dnes.hr_lost', '心拍が途切れた', '心率中断', 'пульс пропал', 'se cortó el pulso', 'Puls ausgefallen', 'pouls perdu', 'pulso perdido')
_tr7('dnes.hr_off', '心拍の受信はオフ', '心率接收已关闭', 'приём пульса выключен', 'recepción del pulso apagada', 'Pulsempfang aus', 'réception du pouls désactivée', 'recebimento do pulso desligado')
_tr7('dnes.hr_busy', 'ポートが使用中', '端口被占用', 'порт занят', 'puerto ocupado', 'Port belegt', 'port occupé', 'porta ocupada')
_tr7('dnes.hr_no_client', '電話がつながらない', '手机没有连上', 'телефон не подключился', 'el móvil no se conectó', 'Handy nicht verbunden', 'téléphone non connecté', 'o celular não conectou')
_tr7('kamae.lost_sub', '心拍が届かなくなりました（時計、電話、または Wi‑Fi）。戻るまでは何も計測せず、自分から声をかけることもありません。', '心率不再传过来了（手表、手机或 Wi‑Fi）。在它恢复之前，我什么都不测量，也不会主动出声。', 'Пульс перестал приходить (часы, телефон или Wi‑Fi). Пока он не вернётся, я ничего не измеряю и сама голос не подам.', 'El pulso dejó de llegar (reloj, móvil o Wi‑Fi). Hasta que vuelva, no mido nada ni aviso por mi cuenta.', 'Der Puls kommt nicht mehr an (Uhr, Handy oder WLAN). Bis er zurück ist, messe ich nichts und melde mich nicht von selbst.', 'Le pouls a cessé d’arriver (montre, téléphone ou Wi‑Fi). Tant qu’il n’est pas revenu, je ne mesure rien et je ne me manifeste pas de moi-même.', 'O pulso parou de chegar (relógio, celular ou Wi‑Fi). Até ele voltar, não meço nada e não aviso sozinha.')
_tr7('log.hr_back', '{s} 秒の途切れのあと、心拍が戻りました。', '无信号 {s} 秒后，心率恢复了。', 'Пульс вернулся после {s} с без сигнала.', 'El pulso ha vuelto tras {s} s sin señal.', 'Der Puls ist nach {s} s ohne Signal zurück.', 'Le pouls est revenu après {s} s sans signal.', 'O pulso voltou depois de {s} s sem sinal.')
_tr7('session.end.none_never', '負荷は一度もしきい値を超えませんでした — 声をかける理由がありませんでした。', '负荷一次都没有超过阈值——我没有理由出声。', 'Нагрузка ни разу не поднялась выше порога — мне не было повода подать голос.', 'La carga no superó el umbral ni una vez — no tenía por qué avisar.', 'Die Last ist kein einziges Mal über die Schwelle gekommen — ich hatte keinen Grund, mich zu melden.', 'La charge n’a pas une seule fois dépassé le seuil — je n’avais aucune raison de me manifester.', 'A carga não passou do limiar nem uma vez — eu não tinha motivo para avisar.')
_tr7('session.end.none_dropouts', '数えている最中に心拍が {n} 回途切れ、そのたびに数え直しになりました。心拍は時計から電話へ Bluetooth で、電話から PC へ Wi‑Fi で届きます — 時計は電話のそばに、電話は Wi‑Fi ルーターの近くに置いてください。', '心率有 {n} 次恰好在计时过程中中断，每次计时都得从头开始。心率从手表通过蓝牙传到手机，再从手机通过 Wi‑Fi 传到电脑——让手表靠近手机，手机靠近 Wi‑Fi 路由器。', 'Пульс {n}× пропадал как раз во время подсчёта, и подсчёт каждый раз начинался заново. Пульс идёт с часов на телефон по Bluetooth, а с телефона по Wi‑Fi на компьютер — держи часы рядом с телефоном, а телефон поближе к Wi‑Fi роутеру.', 'El pulso se cortó {n}× justo durante el conteo, y cada vez el conteo empezó de nuevo. El pulso va del reloj al móvil por Bluetooth y del móvil al PC por Wi‑Fi — ten el reloj cerca del móvil y el móvil cerca del router Wi‑Fi.', 'Der Puls ist {n}× genau während des Zählens ausgefallen, und das Zählen begann jedes Mal von vorn. Der Puls geht von der Uhr per Bluetooth zum Handy und vom Handy über WLAN zum PC — halte die Uhr beim Handy und das Handy nah am WLAN-Router.', 'Le pouls a décroché {n}× pile pendant le comptage, et le comptage a chaque fois recommencé à zéro. Le pouls passe de la montre au téléphone par Bluetooth, et du téléphone à l’ordinateur par Wi‑Fi — garde la montre près du téléphone et le téléphone près du routeur Wi‑Fi.', 'O sinal do pulso caiu {n}× justamente durante a contagem, e a contagem recomeçou do zero toda vez. O pulso vai do relógio para o celular por Bluetooth, e do celular para o PC por Wi‑Fi — mantenha o relógio perto do celular e o celular perto do roteador Wi‑Fi.')
_tr7('session.end.none_nopause', 'ずっと、入力の休みを一度もとらえられませんでした — キーボード、マウス、コントローラーから数秒離れることさえも。声をかける前に待っているのは、まさにその休みです。何かが休みなく入力を送っているのかもしれません。たとえばコントローラーのモーションセンサー（ジャイロ）や、デッドゾーンのないスティック。コントローラーでプレイしているなら、ジャイロをオフにしてみてください。', '整个过程中，我一次输入停顿都没捕捉到——连几秒钟不碰键盘、鼠标或手柄的时候都没有。而我正是要等这样的停顿才出声。可能有东西在不间断地报告输入，比如手柄的体感传感器（陀螺仪）或者没有死区的摇杆。如果你用手柄玩，试试把它的陀螺仪关掉。', 'Всё это время я не поймала ни одной паузы во вводе — даже нескольких секунд без клавиатуры, мыши или геймпада. А именно её я жду, прежде чем подать голос. Возможно, что-то сообщает о вводе без перерыва, например датчик движения геймпада (гироскоп) или стик без мёртвой зоны. Если играешь с геймпадом, попробуй выключить в нём гироскоп.', 'En todo el rato no detecté ni una sola pausa en la entrada — ni unos segundos sin teclado, ratón o mando. Y es justo lo que espero antes de avisar. Puede que algo esté enviando entrada sin parar, por ejemplo el sensor de movimiento del mando (giroscopio) o un stick sin zona muerta. Si juegas con mando, prueba a desactivarle el giroscopio.', 'Die ganze Zeit habe ich keine einzige Pause in deiner Eingabe erwischt — nicht mal ein paar Sekunden ohne Tastatur, Maus oder Controller. Und genau darauf warte ich, bevor ich mich melde. Vielleicht sendet etwas ununterbrochen Eingaben, zum Beispiel der Bewegungssensor des Controllers (Gyro) oder ein Stick ohne Deadzone. Wenn du mit Controller spielst, probier, das Gyro darin auszuschalten.', 'Pendant tout ce temps, je n’ai pas capté une seule pause dans tes entrées — pas même quelques secondes sans clavier, souris ou manette. Et c’est justement elle que j’attends avant de me manifester. Quelque chose signale peut-être des entrées sans arrêt, par exemple le capteur de mouvement de la manette (gyro) ou un stick sans zone morte. Si tu joues à la manette, essaie d’y désactiver le gyro.', 'O tempo todo não detectei nenhuma pausa na entrada — nem alguns segundos sem teclado, mouse ou controle. E é justamente por ela que eu espero antes de avisar. Talvez algo esteja registrando entrada sem parar, como o sensor de movimento do controle (giroscópio) ou um analógico sem zona morta. Se você joga com controle, tente desativar o giroscópio dele.')
_tr7('session.end.none_withheld', '負荷は十分長く高いままでしたが、ちょうどいい瞬間が来ませんでした — まだ上がり続けていたか、心拍が「ピーク」の帯にありました。黙っているほうを選びました。', '负荷持续偏高的时间已经够长了，但合适的时机一直没来——要么它还在上升，要么心率处于高峰区间。我宁可保持安静。', 'Нагрузка держалась высокой достаточно долго, но подходящий момент так и не настал — она либо ещё росла, либо пульс был в пиковой зоне. Я предпочла промолчать.', 'La carga estuvo alta bastante tiempo, pero no llegó el momento adecuado — o aún subía, o el pulso estaba en la zona de pico. Preferí quedarme callada.', 'Die Last war lange genug oben, aber der passende Moment kam nicht — entweder stieg sie noch, oder dein Puls war im Spitzenbereich. Ich habe lieber geschwiegen.', 'La charge est restée haute assez longtemps, mais le bon moment n’est pas venu — soit elle montait encore, soit ton pouls était en zone de pic. J’ai préféré me taire.', 'A carga ficou alta por tempo suficiente, mas o momento certo não chegou — ou ela ainda estava subindo, ou o pulso estava na zona de pico. Preferi ficar calada.')
_tr7('session.end.none_ring', '合図の準備はできていましたが、画面では心拍が高いときの呼吸の輪が呼吸していたので、合図は控えました。', '提示已经准备好了，但屏幕上正有心率高时的呼吸环在呼吸，所以我先没有发出它。', 'Подсказка была готова, но на экране как раз дышало дыхательное кольцо при высоком пульсе, поэтому я её придержала.', 'Había un aviso listo, pero en la pantalla estaba respirando el anillo de respiración por pulso alto, así que lo retuve.', 'Ein Hinweis war bereit, aber auf dem Bildschirm atmete gerade der Atemring bei hohem Puls, also habe ich ihn zurückgehalten.', 'Un rappel était prêt, mais l’anneau de respiration pour pouls élevé respirait à l’écran, alors je l’ai retenu.', 'Um aviso estava pronto, mas o anel de respiração de pulso alto estava respirando na tela, então eu o segurei.')
_tr7('session.end.none_blocked', '合図の準備はできていましたが、そのときは出せませんでした — 画面にすでに画像が出ていたか、時計が歩数を記録していたか、画像がすべてオフでした。', '提示已经准备好了，但那一刻没法出现——屏幕上已经有图片、手表正在记录步数，或者图片全都关掉了。', 'Подсказка была готова, но в тот момент не могла прийти — на экране уже была картинка, часы фиксировали шаги или все картинки были выключены.', 'Había un aviso listo, pero en ese momento no podía llegar — ya había una imagen en pantalla, tu reloj registraba pasos o todas las imágenes estaban desactivadas.', 'Ein Hinweis war bereit, konnte in dem Moment aber nicht kommen — auf dem Bildschirm war schon ein Bild, deine Uhr meldete Schritte, oder alle Bilder waren aus.', 'Un rappel était prêt, mais il ne pouvait pas venir à ce moment-là — une image était déjà à l’écran, ta montre signalait des pas, ou toutes les images étaient désactivées.', 'Um aviso estava pronto, mas não podia chegar naquele momento — já havia uma imagem na tela, o seu relógio registrava passos ou todas as imagens estavam desligadas.')
_tr7('data.hint', '心拍、セッション、気づきはこのコンピューターに残ります。設定も同じです — ただし合図の文面は別です。自然な音声（Edge、既定）で話すとき、私は音声に変換するためにその文面を Microsoft に送ります。Windows の音声は何も送りません。', '你的心率、记录和分析结论都留在这台电脑上。设置也是，只有提示的文字例外：当提示用自然语音（Edge，默认）朗读时，我会把它们的文字发送给 Microsoft 的服务转换成语音。Windows 语音不会发送任何东西。', 'Твой пульс, сессии и наблюдения остаются на этом компьютере. Настройки тоже, кроме текста подсказок: когда они звучат естественным голосом (Edge, по умолчанию), я отправляю их текст сервису Microsoft для преобразования в речь. Голос Windows ничего не отправляет.', 'Tu pulso, tus sesiones y las observaciones se quedan en este ordenador. Los ajustes también, salvo el texto de los avisos: cuando hablan con la voz natural (Edge, la predeterminada), envío su texto al servicio de Microsoft para convertirlo en voz. La voz de Windows no envía nada.', 'Dein Puls, deine Sitzungen und Beobachtungen bleiben auf diesem Rechner. Die Einstellungen auch, bis auf den Text der Hinweise: Wenn sie mit der natürlichen Stimme sprechen (Edge, Standard), schicke ich ihren Text an Microsoft, um ihn in Sprache umzuwandeln. Die Windows-Stimme schickt nichts.', 'Ton pouls, tes séances et les observations restent sur cet ordinateur. Les réglages aussi, sauf le texte des rappels : quand ils parlent avec la voix naturelle (Edge, par défaut), j’envoie leur texte au service Microsoft pour le convertir en parole. La voix Windows n’envoie rien.', 'O seu pulso, as sessões e as observações ficam neste computador. As configurações também, exceto o texto dos avisos: quando eles falam com a voz natural (Edge, a padrão), eu envio o texto deles ao serviço da Microsoft para convertê-lo em fala. A voz do Windows não envia nada.')
_tr7('data.delete.legacy', '古いバージョンのアプリが残したコピー（フォルダー「{folder}」）', '旧版应用留下的副本（文件夹“{folder}”）', 'копии от старой версии приложения (папка «{folder}»)', 'copias de una versión anterior de la app (carpeta «{folder}»)', 'Kopien aus einer älteren Version der App (Ordner „{folder}“)', 'copies d’une ancienne version de l’app (dossier « {folder} »)', 'cópias de uma versão mais antiga do app (pasta “{folder}”)')
_tr7('data.export.btn', '履歴をエクスポート（JSON）', '导出历史（JSON）', 'Экспортировать историю (JSON)', 'Exportar historial (JSON)', 'Verlauf exportieren (JSON)', 'Exporter l’historique (JSON)', 'Exportar histórico (JSON)')
_tr7('data.import.flagged', 'インポートした記録には、あなたのものではないという印がつきます。「履歴」には表示されますが、私はそこから学びません。安静時ベースライン、高心拍の上限、私が声をかけるしきい値、気づき、合図のグラフ、前回のセッションのカード、そして私が音声で声をかけるか、画像で知らせるか、休むかの判断には入りません。別のコンピューターからのあなた自身のエクスポートでも同じです。', '导入的记录会被标记为“外来”。你能在“历史”里看到它们，但我不会从中学习：它们不会计入你的静息基线、高心率上限和我出声所依据的负荷阈值，也不会进入分析结论、提示图表、最近一次记录的卡片，也不会影响我是用语音、图片提示还是暂停提示。你自己从另一台电脑导出的数据也是如此。', 'Импортированные записи помечаются как чужие. В «Истории» ты их увидишь, но я на них не учусь: они не входят ни в твою базовую линию покоя, ни в границу высокого пульса, ни в порог, от которого я подаю голос, ни в наблюдения, ни в график о подсказках, ни в карточку последней сессии, ни в выбор, подаю ли я голос, показываю картинку или беру паузу. Это касается и твоего собственного экспорта с другого компьютера.', 'Los registros importados se marcarán como ajenos. Los verás en el Historial, pero yo no aprendo de ellos: no entran en tu línea base en reposo, ni en el límite de pulso alto, ni en el umbral a partir del cual aviso, ni en las observaciones, el gráfico de avisos o la tarjeta de la última sesión, ni en si aviso con voz, con imagen o me tomo una pausa. Esto vale también para tu propia exportación desde otro ordenador.', 'Importierte Einträge werden als fremd markiert. Im Verlauf siehst du sie, aber ich lerne nicht aus ihnen: Sie fließen weder in deine Ruhebasislinie noch in deine Grenze für hohen Puls oder die Schwelle ein, ab der ich mich melde, auch nicht in die Beobachtungen, das Diagramm zu den Hinweisen, die Karte der letzten Sitzung und nicht in die Entscheidung, ob ich mich mit Stimme oder Bild melde oder eine Pause einlege. Das gilt auch für deinen eigenen Export von einem anderen Rechner.', 'Les enregistrements importés sont marqués comme étrangers. Tu les verras dans l’Historique, mais je n’en apprends rien : ils n’entrent ni dans ta ligne de base au repos, ni dans ta limite de pouls élevé, ni dans le seuil à partir duquel je me manifeste, ni dans les observations, le graphique des rappels ou la carte de la dernière séance, ni dans le choix de me manifester par la voix, par l’image ou de faire une pause. Cela vaut aussi pour ton propre export depuis un autre ordinateur.', 'Os registros importados são marcados como externos. Você vai vê-los no Histórico, mas eu não aprendo com eles: não entram na sua linha de base em repouso, no seu limite de pulso alto nem no limiar a partir do qual eu aviso, nas observações, no gráfico dos avisos, no cartão da última sessão, nem na decisão de eu avisar com voz, com imagem ou fazer uma pausa. Isso vale também para uma exportação sua de outro computador.')
_tr7('data.import.question', 'あなたのものと統合しますか？ それとも、これで置き換えますか？', '把它们和你的合并，还是用它们替换你的？', 'Объединить их с твоими или заменить ими твои?', '¿Combinarlos con los tuyos o reemplazar los tuyos por ellos?', 'Mit deinen zusammenführen oder deine durch sie ersetzen?', 'Les fusionner avec les tiens, ou remplacer les tiens par eux ?', 'Juntar com os seus ou substituir os seus por eles?')
_tr7('data.import.replace_confirm', '置き換えると、セッション履歴と測定ウィンドウがファイルの内容で上書きされます。その前に、元のファイルの隣にバックアップとして取っておきます（名前に「pred-importom」が入ります）。本当に置き換えますか？', '替换会用文件内容覆盖你的记录历史和测量窗口。在此之前，我会把它们作为备份放在原文件旁边（文件名中带有“pred-importom”）。确定要替换吗？', 'Замена перезапишет твою историю сессий и измерительные окна содержимым файла. Перед этим я отложу их как резервную копию рядом с исходными файлами (с «pred-importom» в названии). Точно заменить?', 'Reemplazar sobrescribe tu historial de sesiones y las ventanas de medición con el contenido del archivo. Antes los guardaré como copia de seguridad junto a los archivos originales (con «pred-importom» en el nombre). ¿Reemplazar de verdad?', 'Beim Ersetzen werden dein Sitzungsverlauf und die Messfenster mit dem Inhalt der Datei überschrieben. Vorher lege ich sie als Sicherung neben die ursprünglichen Dateien (mit „pred-importom“ im Namen). Wirklich ersetzen?', 'Remplacer écrase ton historique des séances et tes fenêtres de mesure avec le contenu du fichier. Avant ça, je les mets de côté comme sauvegarde à côté des fichiers d’origine (avec « pred-importom » dans le nom). Vraiment remplacer ?', 'Substituir sobrescreve o seu histórico de sessões e as janelas de medição com o conteúdo do arquivo. Antes disso, eu os guardo como cópia de segurança ao lado dos arquivos originais (com “pred-importom” no nome). Substituir mesmo?')
_tr7('data.import.replace_yes', 'はい、置き換える', '是，替换', 'Да, заменить', 'Sí, reemplazar', 'Ja, ersetzen', 'Oui, remplacer', 'Sim, substituir')
_tr7('data.import.back', '戻る', '返回', 'Назад', 'Atrás', 'Zurück', 'Retour', 'Voltar')
_tr7('data.import.backup', '元のファイルをバックアップとして取っておきました：{files}', '我已把原文件作为备份保存：{files}', 'Исходные файлы я отложила как резервную копию: {files}', 'He guardado los archivos originales como copia de seguridad: {files}', 'Die ursprünglichen Dateien habe ich als Sicherung beiseitegelegt: {files}', 'J’ai mis les fichiers d’origine de côté comme sauvegarde : {files}', 'Guardei os arquivos originais como cópia de segurança: {files}')
_tr7('world.play', 'ゲーム', '游戏', 'Игра', 'Juego', 'Spiel', 'Jeu', 'Jogo')
_tr7('world.work', '仕事', '工作', 'Работа', 'Trabajo', 'Arbeit', 'Travail', 'Trabalho')
_tr7('world.tip', 'ワールド：ゲームか仕事か — それぞれに独自の履歴と見た目があります。\n仕事中は画像だけで知らせます。進行中のセッションは、始まったワールドにとどまります。', '世界：游戏或工作——各自有独立的历史和外观。\n工作时我只用图片提示。进行中的记录会留在它开始时所在的世界。', 'Мир: игра или работа — у каждого своя история и внешний вид.\nНа работе я даю о себе знать только картинкой. Идущая сессия остаётся в мире, в котором началась.', 'Mundo: juego o trabajo — cada uno tiene su propio historial y aspecto.\nEn el trabajo solo aviso con imagen. Una sesión en curso se queda en el mundo en el que empezó.', 'Welt: Spiel oder Arbeit — jede hat ihren eigenen Verlauf und ihr eigenes Aussehen.\nBei der Arbeit melde ich mich nur mit Bild. Eine laufende Sitzung bleibt in der Welt, in der sie begonnen hat.', 'Monde : jeu ou travail — chacun a son propre historique et son apparence.\nAu travail, je ne me manifeste que par l’image. Une séance en cours reste dans le monde où elle a commencé.', 'Mundo: jogo ou trabalho — cada um tem o próprio histórico e a própria aparência.\nNo Trabalho, só aviso com imagem. Uma sessão em andamento fica no mundo em que começou.')
_tr7('settings.world', 'ワールド', '世界', 'Мир', 'Mundo', 'Welt', 'Monde', 'Mundo')
_tr7('settings.world_sub', 'ゲームは Sumi、仕事は Aizome。ワールドごとに独自の履歴と気づきがあります。仕事中は画像だけで知らせます — 音声も効果音もなし。安静時ベースラインは共通です — 体はひとつですから。高心拍の上限と負荷のしきい値は、ゲームからだけ算出します。', '游戏是 Sumi，工作是 Aizome。每个世界都有自己的历史和分析结论。工作时我只用图片提示——没有语音和音效。静息基线是共用的，毕竟身体只有一个；高心率上限和负荷阈值我只根据游戏计算。', 'Игра — это Sumi, работа — Aizome. У каждого мира своя история и наблюдения. На работе я даю о себе знать только картинкой — без голоса и звука. Базовая линия покоя общая, тело ведь одно; границу высокого пульса и порог нагрузки я считаю только по игре.', 'El juego es Sumi; el trabajo, Aizome. Cada mundo tiene su propio historial y sus observaciones. En el trabajo solo aviso con imagen — sin voz ni sonido. La línea base en reposo es común, el cuerpo es uno; el límite de pulso alto y el umbral de carga los calculo solo a partir del juego.', 'Spiel ist Sumi, Arbeit ist Aizome. Jede Welt hat ihren eigenen Verlauf und eigene Beobachtungen. Bei der Arbeit melde ich mich nur mit Bild — ohne Stimme und Ton. Die Ruhebasislinie ist gemeinsam, es ist ein Körper; die Grenze für hohen Puls und die Lastschwelle berechne ich nur aus dem Spielen.', 'Le jeu, c’est Sumi ; le travail, Aizome. Chaque monde a son propre historique et ses observations. Au travail, je ne me manifeste que par l’image — sans voix ni son. La ligne de base au repos est commune, le corps est le même ; la limite de pouls élevé comme le seuil de charge, je ne les calcule qu’à partir du jeu.', 'Jogo é Sumi, Trabalho é Aizome. Cada mundo tem o próprio histórico e as próprias observações. No Trabalho, só aviso com imagem — sem voz e sem som. A linha de base em repouso é compartilhada, o corpo é um só; o limite de pulso alto e o limiar de carga eu calculo só a partir do jogo.')
_tr7('history.world_note', 'ワールド：{world}。ラベルのない古いセッションは「ゲーム」に入ります。「{chart}」グラフは、ゲームで鳴った合図だけを数えます — 仕事中は画像だけで知らせるからです。', '世界：{world}。没有标签的旧记录归入“游戏”。“{chart}”图表只统计游戏中出声的提示——工作时我只用图片提示。', 'Мир: {world}. Старые сессии без метки относятся к «Игре». График «{chart}» учитывает только прозвучавшие подсказки из игры — на работе я даю о себе знать только картинкой.', 'Mundo: {world}. Las sesiones antiguas sin etiqueta pertenecen a Juego. El gráfico «{chart}» cuenta solo los avisos del juego que sonaron — en el trabajo solo aviso con imagen.', 'Welt: {world}. Ältere Sitzungen ohne Kennzeichnung gehören zur Welt Spiel. Das Diagramm „{chart}“ zählt nur Hinweise aus dem Spiel, die erklungen sind — bei der Arbeit melde ich mich nur mit Bild.', 'Monde : {world}. Les anciennes séances sans étiquette appartiennent au Jeu. Le graphique « {chart} » ne compte que les rappels du jeu qui ont retenti — au travail, je ne me manifeste que par l’image.', 'Mundo: {world}. Sessões antigas sem rótulo contam como Jogo. O gráfico “{chart}” conta só os avisos do Jogo que tocaram — no Trabalho, só aviso com imagem.')
_tr7('ob.step4.title', 'メインのワールドを選ぶ', '选择你的主世界', 'Выбери основной мир', 'Elige tu mundo principal', 'Wähle deine Hauptwelt', 'Choisis ton monde principal', 'Escolha o seu mundo principal')
_tr7('ob.step4.body', '右上でいつでも切り替えられます。ワールドごとに独自の履歴と見た目があります。あなた自身の限界値は「ゲーム」からだけ学びます。', '随时可以在右上角切换。每个世界都有自己的历史和外观。你自己的界限，我只从“游戏”里学习。', 'Переключить его можно когда угодно справа вверху. У каждого мира своя история и внешний вид. Твои собственные границы я узнаю только по «Игре».', 'Lo cambias cuando quieras arriba a la derecha. Cada mundo tiene su propio historial y aspecto. Tus propios límites los aprendo solo de Juego.', 'Du kannst sie jederzeit oben rechts wechseln. Jede Welt hat ihren eigenen Verlauf und ihr eigenes Aussehen. Deine eigenen Grenzen lerne ich nur aus Spiel.', 'Tu le changes à tout moment en haut à droite. Chaque monde a son propre historique et son apparence. Tes propres limites, je ne les apprends qu’en Jeu.', 'Dá para trocar a qualquer momento no canto superior direito. Cada mundo tem o próprio histórico e a própria aparência. Seus próprios limites eu aprendo só no Jogo.')
_tr7('ob.world.play.title', 'ゲーム · 墨 Sumi', '游戏 · 墨 Sumi', 'Игра · 墨 Sumi', 'Juego · 墨 Sumi', 'Spiel · 墨 Sumi', 'Jeu · 墨 Sumi', 'Jogo · 墨 Sumi')
_tr7('ob.world.play.desc', 'プレイするとき。合間に合図、たいていは音声つき。\n墨に金。', '玩游戏时。提示出现在间歇里，大多带语音。\n墨与金。', 'Когда играешь. Подсказки в паузах, чаще с голосом.\nТушь с золотом.', 'Cuando juegas. Avisos en las pausas, casi siempre con voz.\nTinta con oro.', 'Wenn du spielst. Hinweise in den Pausen, meist mit Stimme.\nTinte mit Gold.', 'Quand tu joues. Des rappels dans les pauses, surtout avec la voix.\nEncre et or.', 'Para quando você joga. Avisos nas pausas, geralmente com voz.\nNanquim com ouro.')
_tr7('ob.world.work.title', '仕事 · 藍 Aizome', '工作 · 藍 Aizome', 'Работа · 藍 Aizome', 'Trabajo · 藍 Aizome', 'Arbeit · 藍 Aizome', 'Travail · 藍 Aizome', 'Trabalho · 藍 Aizome')
_tr7('ob.world.work.desc', '仕事をするとき。合図は画像だけ、音声も効果音もなし。\n藍色。', '工作时。提示只用图片，没有语音和音效。\n靛蓝。', 'Когда работаешь. Подсказки только картинкой, без голоса и звука.\nИндиго.', 'Cuando trabajas. Avisos solo con imagen, sin voz ni sonido.\nÍndigo.', 'Wenn du arbeitest. Hinweise nur als Bild, ohne Stimme und Ton.\nIndigo.', 'Quand tu travailles. Des rappels seulement en image, sans voix ni son.\nIndigo.', 'Para quando você trabalha. Avisos só com imagem, sem voz e sem som.\nÍndigo.')
_tr7('session.end.title_work', '{time} 仕事をした。', '你工作了 {time}。', 'За тобой {time} работы.', 'Trabajaste {time}.', 'Du hast {time} gearbeitet.', 'Tu as travaillé {time}.', 'Você trabalhou por {time}.')
_tr7('session.end.cues_work', '{n} 回合図を出した — 仕事中なので、画像だけで音声も効果音もなし。', '我提醒了 {n} 次——工作时只用图片，没有语音和音效。', 'Я дала о себе знать {n}× — на работе только картинкой, без голоса и звука.', 'Te avisé {n} veces — en el trabajo solo con imagen, sin voz ni sonido.', 'Ich habe mich {n}× gemeldet — bei der Arbeit nur mit Bild, ohne Stimme und Ton.', 'Je me suis manifestée {n}× — au travail seulement par l’image, sans voix ni son.', 'Avisei {n}× — no Trabalho, só com imagem, sem voz e sem som.')
_tr7('settings.hr_critical_computed', 'あなたの高心拍の上限：{bpm} BPM — あなたのゲームセッション {n} 回から算出しました。設定するものではなく、あなたを知るにつれて私が調整します。', '你的高心率上限：{bpm} BPM——是我根据你的 {n} 次游戏记录算出来的。它不需要设置，我会随着对你的了解调整它。', 'Твоя граница высокого пульса: {bpm} BPM — я вычислила её по твоим игровым сессиям ({n}). Это не настройка: я уточню её, по мере того как узнаю тебя.', 'Tu límite de pulso alto: {bpm} BPM — lo calculé a partir de {n} de tus sesiones de juego. No se ajusta; lo iré adaptando a medida que te conozca.', 'Deine Grenze für hohen Puls: {bpm} BPM — ich habe sie aus {n} deiner Spielsitzungen berechnet. Sie wird nicht eingestellt; ich passe sie an, während ich dich kennenlerne.', 'Ta limite de pouls élevé : {bpm} BPM — je l’ai calculée à partir de {n} de tes séances de jeu. Elle ne se règle pas ; je l’ajuste à mesure que je te connais.', 'O seu limite de pulso alto: {bpm} BPM — calculei a partir de {n} das suas sessões de jogo. Não é uma configuração; eu o ajusto conforme vou te conhecendo.')
_tr7('settings.hr_critical_learning', '高心拍の上限：今のところ {bpm} BPM。各5分以上のゲームセッションをあと {treba} 回行えば、あなた自身の上限を算出します。', '高心率上限：目前为 {bpm} BPM。再有 {treba} 次每次至少 5 分钟的游戏记录后，我会算出你自己的上限。', 'Граница высокого пульса: пока {bpm} BPM. Твою я вычислю после ещё нескольких игровых сессий не короче 5 минут (осталось: {treba}).', 'Límite de pulso alto: por ahora {bpm} BPM. Calcularé el tuyo tras {treba} sesiones de juego más, de al menos 5 minutos cada una.', 'Grenze für hohen Puls: vorerst {bpm} BPM. Deine berechne ich nach {treba} weiteren Spielsitzungen von je mindestens 5 Minuten.', 'Limite de pouls élevé : {bpm} BPM pour l’instant. Je calculerai la tienne après {treba} séances de jeu de plus, d’au moins 5 minutes chacune.', 'Limite de pulso alto: por enquanto {bpm} BPM. Calculo o seu depois de mais {treba} sessões de jogo, cada uma com pelo menos 5 minutos.')
_tr7('cue_rate.computed', '負荷がしきい値 {prah}/100 を {hold} 秒超えたら合図を出します — このしきい値は、あなたのゲームセッション {n} 回から、プレイ時間の5分の1がそれを上回る水準として算出しました。1時間に最大 {strop} 回、間隔は {odstup} 分以上。', '当你的负荷在阈值 {prah}/100 以上保持 {hold} 秒时，我会提醒你——这个阈值是我根据你的 {n} 次游戏记录算出的：你有五分之一的游戏时间处在它之上。每小时最多 {strop} 次，间隔至少 {odstup} 分钟。', 'Я подаю знак, когда твоя нагрузка держится {hold} с выше порога {prah} из 100 — этот порог я вычислила по {n} твоим игровым сессиям как уровень, выше которого ты проводишь пятую часть игры. Не чаще {strop}× в час, с перерывом не меньше {odstup} мин.', 'Aviso cuando tu carga se mantiene {hold} s por encima del umbral de {prah} sobre 100: lo calculé a partir de {n} de tus sesiones de juego como el nivel por encima del cual pasas una quinta parte del tiempo de juego. Como mucho {strop}× por hora, con al menos {odstup} min entre avisos.', 'Ich melde mich, wenn deine Last {hold} s über der Schwelle von {prah} von 100 bleibt — diese Schwelle habe ich aus {n} deiner Spielsitzungen berechnet: Über ihr verbringst du ein Fünftel deiner Spielzeit. Höchstens {strop}× pro Stunde, mindestens {odstup} Min. Abstand.', 'Je me manifeste quand ta charge reste {hold} s au-dessus du seuil de {prah} sur 100 — je l’ai calculé à partir de {n} de tes séances de jeu comme le niveau au-dessus duquel tu passes un cinquième de ton temps de jeu. Au plus {strop}× par heure, avec au moins {odstup} min d’écart.', 'Aviso quando a sua carga fica {hold} s acima do limiar de {prah} de 100 — calculei esse limiar a partir de {n} das suas sessões de jogo como o nível acima do qual você passa um quinto do tempo de jogo. No máximo {strop}× por hora, com pelo menos {odstup} min de intervalo.')
_tr7('cue_rate.learning', '今のところは平均的なプレイヤーの数値です：負荷がしきい値 {prah}/100 を {hold} 秒超えたら合図を出します。あなた自身のしきい値はゲームのセッションから算出します。', '目前用的是普通玩家的数值：负荷在阈值 {prah}/100 以上保持 {hold} 秒时，我会提醒你。你自己的阈值我会根据游戏记录来算。', 'Пока действуют числа для среднего игрока: я подам знак, когда нагрузка продержится {hold} с выше порога {prah} из 100. Твой порог я вычислю по игровым сессиям.', 'Por ahora valen los números de un jugador medio: aviso cuando la carga se mantiene {hold} s por encima del umbral de {prah} sobre 100. Tu propio umbral lo calcularé a partir de tus sesiones de juego.', 'Vorerst gelten die Zahlen eines durchschnittlichen Spielers: Ich melde mich, wenn die Last {hold} s über der Schwelle von {prah} von 100 bleibt. Deine eigene Schwelle berechne ich aus deinen Spielsitzungen.', 'Pour l’instant, ce sont les chiffres d’un joueur moyen : je me manifeste quand la charge reste {hold} s au-dessus du seuil de {prah} sur 100. Je calculerai ton propre seuil à partir de tes séances de jeu.', 'Por enquanto valem os números de um jogador médio: aviso quando a carga fica {hold} s acima do limiar de {prah} de 100. O seu próprio limiar eu calculo a partir das suas sessões de jogo.')
_tr7('session.felt.cue.agitated', 'かき乱された', '让我烦躁', 'взвинтила меня', 'me alteró', 'hat mich aufgewühlt', 'm’a tapé sur les nerfs', 'me tirou do eixo')
_tr7('history.rebrik.visual', '今は画像だけで知らせていて、音は出していません。{dovod} 合図のあったセッションが不満なく続いたら、音を戻します（あと {n} 回必要）。', '现在我只用图片提示，没有声音。{dovod} 等之后几次有提示的记录都没有异议时，我会恢复声音（还需要：{n} 次）。', 'Сейчас я даю о себе знать только картинкой, без звука. {dovod} Звук верну, когда следующие сессии с подсказкой пройдут без нареканий (нужно ещё: {n}).', 'Por ahora solo aviso con imagen, sin sonido. {dovod} Devolveré el sonido cuando más sesiones con aviso pasen sin quejas (faltan: {n}).', 'Im Moment melde ich mich nur mit Bild, ohne Ton. {dovod} Den Ton bringe ich zurück, wenn weitere Sitzungen mit Hinweis ohne Einwände vergehen (noch nötig: {n}).', 'Pour l’instant, je ne me manifeste que par l’image, sans son. {dovod} Je remettrai le son quand d’autres séances avec un rappel se seront passées sans objection (encore nécessaires : {n}).', 'Por enquanto só aviso com imagem, sem som. {dovod} Trago o som de volta quando mais sessões com aviso passarem sem queixas (ainda faltam: {n}).')
_tr7('history.rebrik.pause', '今は合図をオフにしています。{dovod} 5分以上のセッションをあと何回か重ねたら、画像でもう一度試します（あと {n} 回必要）。合図がなくて物足りなければ、セッション後のアンケートで「はい、あった」と答えてください。次のセッションからまた試します。', '我现在关闭了提示。{dovod} 再有几次至少 5 分钟的记录后，我会用图片再试一次（还需要：{n} 次）。如果你想念这些提示，就在记录结束后的问卷里选“有，该提醒”，从下一次记录起我会再试。', 'Подсказки у меня сейчас выключены. {dovod} Картинкой попробую снова после следующих сессий хотя бы по 5 минут (нужно ещё: {n}). Если тебе не хватает подсказок, в опросе после сессии ответь «да, стоило» — и со следующей сессии я попробую снова.', 'Ahora tengo los avisos desactivados. {dovod} Volveré a probar con imagen tras más sesiones de al menos 5 minutos (faltan: {n}). Si echas de menos los avisos, responde «sí, debió» en el cuestionario tras la sesión y lo volveré a intentar desde la siguiente.', 'Die Hinweise habe ich im Moment ausgeschaltet. {dovod} Mit Bild probiere ich es wieder nach weiteren Sitzungen von mindestens 5 Minuten (noch nötig: {n}). Wenn dir die Hinweise fehlen, antworte im Fragebogen nach der Sitzung „ja, hätte sollen“, und ab der nächsten Sitzung probiere ich es wieder.', 'Les rappels sont désactivés pour l’instant. {dovod} Je réessaierai avec l’image après d’autres séances d’au moins 5 minutes (encore nécessaires : {n}). Si les rappels te manquent, réponds « oui, il aurait dû » dans le questionnaire après la séance, et je réessaierai dès la suivante.', 'Os avisos estão desativados por enquanto. {dovod} Vou tentar de novo com imagem depois de mais sessões de pelo menos 5 minutos (ainda faltam: {n}). Se você sente falta dos avisos, responda “sim, devia” no questionário depois da sessão e eu tento de novo a partir da próxima.')
_tr7('history.rebrik.why.disruptive', 'セッション後のアンケートで、合図が邪魔だったと答えました。', '你在记录结束后的问卷里说提示打扰到你了。', 'После сессии в опросе было отмечено, что подсказка мешала.', 'Tras una sesión, dijiste en el cuestionario que el aviso molestó.', 'Nach einer Sitzung hast du im Fragebogen angegeben, dass der Hinweis gestört hat.', 'Après une séance, tu as écrit dans le questionnaire que le rappel avait gêné.', 'Depois de uma sessão, você disse no questionário que o aviso atrapalhou.')
_tr7('history.rebrik.why.agitated', 'セッション後のアンケートで、合図にかき乱されたと答えました。', '你在记录结束后的问卷里说提示让你烦躁。', 'После сессии в опросе было отмечено, что подсказка тебя взвинтила.', 'Tras una sesión, dijiste en el cuestionario que el aviso te alteró.', 'Nach einer Sitzung hast du im Fragebogen angegeben, dass dich der Hinweis aufgewühlt hat.', 'Après une séance, tu as écrit dans le questionnaire que le rappel t’avait tapé sur les nerfs.', 'Depois de uma sessão, você disse no questionário que o aviso te tirou do eixo.')
_tr7('history.rebrik.why.snooze', '合図から1分以内に私を静かにさせ、そのあともセッションが続きました。', '提示后一分钟内你就让我静音了，而记录之后还在继续。', 'В течение минуты после подсказки меня заглушили, а сессия потом ещё продолжалась.', 'Me silenciaste en el minuto siguiente a un aviso, y después la sesión continuó.', 'Innerhalb einer Minute nach einem Hinweis hast du mich stummgeschaltet, und die Sitzung ging danach noch weiter.', 'Moins d’une minute après un rappel, tu m’as mise en sourdine, et la séance a ensuite continué.', 'Você me silenciou menos de um minuto depois de um aviso, e a sessão continuou depois disso.')
_tr7('history.rebrik.why.retry', '静かなセッションを何回か経たので、もう一度試しています。', '安静了几次记录之后，我再试一次。', 'После нескольких тихих сессий пробую снова.', 'Tras unas sesiones de silencio, lo vuelvo a intentar.', 'Nach ein paar stillen Sitzungen versuche ich es wieder.', 'Après quelques séances de silence, je réessaie.', 'Depois de algumas sessões em silêncio, estou tentando de novo.')
_tr7('history.rebrik.why.missed', '私が声をかけるべきだったと答えてくれたので、もう一度試しています。', '你说我当时应该出声，所以我再试一次。', 'В опросе было отмечено, что мне стоило подать голос, — вот и пробую снова.', 'Dijiste que debí avisar, así que lo vuelvo a intentar.', 'Du hast angegeben, dass ich mich hätte melden sollen, also versuche ich es wieder.', 'Tu as écrit que j’aurais dû me manifester, alors je réessaie.', 'Você disse que eu devia ter avisado, então estou tentando de novo.')
_tr7('session.end.cues_visual', '{n} 回合図を出した — 画像だけで、音はなし。', '我提醒了 {n} 次——只用图片，没有声音。', 'Я дала о себе знать {n}× — только картинкой, без звука.', 'Te avisé {n} veces — solo con imagen, sin sonido.', 'Ich habe mich {n}× gemeldet — nur mit Bild, ohne Ton.', 'Je me suis manifestée {n}× — seulement par l’image, sans son.', 'Avisei {n}× — só com imagem, sem som.')
_tr7('session.end.none_paused', 'あなたのフィードバックを受けて、数回のセッションのあいだ合図をオフにしています — 理由は「履歴」にあります。合図がなくて物足りなければ、下で「はい、あった」と答えてください。', '根据你的反馈，我把提示关闭了几次记录——原因可以在“历史”里找到。如果你想念它们，就在下面选“有，该提醒”。', 'После твоего отзыва я выключила подсказки на несколько сессий — почему, найдёшь в «Истории». Если тебе их не хватает, ответь ниже «да, стоило».', 'Tras tu respuesta, tengo los avisos desactivados durante unas sesiones — el porqué está en el Historial. Si los echas de menos, responde abajo «sí, debió».', 'Nach deinem Feedback habe ich die Hinweise für ein paar Sitzungen ausgeschaltet — warum, steht im Verlauf. Wenn sie dir fehlen, antworte unten „ja, hätte sollen“.', 'Suite à tes réponses, j’ai désactivé les rappels pour quelques séances — tu trouveras pourquoi dans l’Historique. S’ils te manquent, réponds ci-dessous « oui, il aurait dû ».', 'Depois do seu feedback, desativei os avisos por algumas sessões — o motivo está no Histórico. Se sentir falta deles, responda “sim, devia” aqui embaixo.')
_tr7('kamae.paused_sub', '心拍は見ていますが、今は合図をオフにしています — 理由は「履歴」にあります。', '我在关注心率，但提示现在是关闭的——原因可以在“历史”里找到。', 'Слежу за пульсом, но подсказки сейчас выключены — почему, найдёшь в «Истории».', 'Vigilo tu pulso, pero ahora tengo los avisos desactivados — el porqué está en el Historial.', 'Ich beobachte deinen Puls, aber die Hinweise sind gerade ausgeschaltet — warum, steht im Verlauf.', 'Je surveille ton pouls, mais les rappels sont désactivés pour l’instant — tu trouveras pourquoi dans l’Historique.', 'Acompanho o seu pulso, mas os avisos estão desativados por enquanto — o motivo está no Histórico.')
_tr7('ob.step5.kicker', 'ステップ 5 / 5', '第 5 步，共 5 步', 'ШАГ 5 из 5', 'PASO 5 de 5', 'SCHRITT 5 von 5', 'ÉTAPE 5 sur 5', 'PASSO 5 de 5')
_tr7('ob.cue.title', 'ゲームで本当にイライラしたとき、アプリにどう知らせてほしいですか？', '当游戏把你惹得够呛时，你希望应用怎样提醒你？', 'Когда игра тебя как следует заведёт, как ты хочешь, чтобы приложение дало о себе знать?', 'Cuando el juego te saca de quicio, ¿cómo quieres que te avise la app?', 'Wenn dich ein Spiel richtig aufregt, wie soll sich die App melden?', 'Quand un jeu te met vraiment à cran, comment veux-tu que l’app se manifeste ?', 'Quando o jogo te tirar mesmo do sério, como você quer que o app avise?')
_tr7('ob.cue.voice', '音声でもかまわない', '用语音也可以', 'Можно и голосом', 'Con voz, sin problema', 'Gern auch mit Stimme', 'Avec la voix, ça me va', 'Pode ser com voz')
_tr7('ob.cue.sound', '効果音と画像だけがいい', '最好只用音效和图片', 'Лучше только звук и картинка', 'Mejor solo sonido e imagen', 'Lieber nur Ton und Bild', 'Plutôt juste un son et une image', 'Prefiro só som e imagem')
_tr7('ob.cue.visual', '画像だけ、何も言わないで', '只要图片，什么都别说', 'Только картинка, ничего не говори', 'Solo imagen, sin hablar', 'Nur ein Bild, sag nichts', 'Juste une image, ne dis rien', 'Só imagem, sem falar nada')
_tr7('ob.cue.unsure', 'わからない — 音声で始めて、邪魔になったら控えめにして', '不确定——先用语音，碍事时再安静下来', 'Не знаю — начни с голоса и стань тише, если будешь мешать', 'No lo sé: empieza con voz y baja el tono si molestas', 'Weiß nicht — fang mit Stimme an und werd leiser, wenn du störst', 'Je ne sais pas — commence avec la voix et fais-toi plus discrète si tu gênes', 'Não sei — comece com voz e baixe o tom se atrapalhar')
_tr7('ob.cue.note', '「設定」→「サウンド」で変えられます。私は自分から控えめにはなっても、大きくなることはありません。最初のうちは、比較のため合図のおよそ4回に1回をわざと画像だけにします。', '可以在“设置 → 声音”里更改。我会自己变安静，但绝不会变响。一开始，大约每四条提示里有一条会故意只显示图片——用来对比。', 'Изменить это можно в «Настройки → Звук». Тише я могу стать и сама, громче — никогда. Поначалу примерно каждую четвёртую подсказку я нарочно показываю только картинкой — для сравнения.', 'Puedes cambiarlo en Ajustes → Sonido. Puedo bajar el tono por mi cuenta, nunca subirlo. Al principio, más o menos uno de cada cuatro avisos va a propósito solo con imagen, para comparar.', 'Ändern kannst du das unter Einstellungen → Ton. Leiser werden kann ich auch von selbst, lauter nie. Anfangs zeige ich etwa jeden vierten Hinweis absichtlich nur als Bild — zum Vergleich.', 'Tu peux le changer dans Paramètres → Son. Je peux me faire plus discrète toute seule, jamais plus bruyante. Au début, environ un rappel sur quatre n’est volontairement qu’une image — pour comparer.', 'Você muda isso em Configurações → Som. Posso baixar o tom sozinha, nunca aumentar. No começo, mais ou menos um aviso em cada quatro vem de propósito só com imagem — para comparar.')
_tr7('settings.cue_style', '合図の出し方', '我怎样出声', 'Как я даю о себе знать', 'Cómo aviso', 'Wie ich mich melde', 'Comment je me manifeste', 'Como eu aviso')
_tr7('settings.cue_style_sub', 'これが私の使う上限で、これより大きくはなりません。合図が邪魔なとき（プレイ後のアンケートや「今はいい」）、自分から控えめにします。仕事中は画像だけです。', '这是我会用的最高程度，绝不会更响。提示碍事时（游戏后的问卷或“现在不要”），我会自己安静下来。工作时只用图片。', 'Это максимум, который я использую, — громче не будет. Если подсказки мешают (опрос после игры или «не сейчас»), я сама становлюсь тише. На работе — только картинкой.', 'Esto es lo máximo que usaré, nunca más fuerte. Si los avisos molestan (el cuestionario tras jugar o «ahora no»), bajo el tono por mi cuenta. En el trabajo, solo imagen.', 'Das ist das Höchste, was ich nutze — lauter nie. Wenn Hinweise stören (Fragebogen nach dem Spiel oder „jetzt nicht“), werde ich von selbst leiser. Bei der Arbeit nur mit Bild.', 'C’est le maximum que j’utiliserai — jamais plus fort. Quand les rappels gênent (le questionnaire après la partie ou « pas maintenant »), je me fais plus discrète toute seule. Au travail, image seulement.', 'Este é o máximo que vou usar — nunca mais alto. Quando os avisos atrapalham (o questionário depois do jogo ou “agora não”), baixo o tom sozinha. No trabalho, só imagem.')
_tr7('dnes.nonstop_input', 'もう {min} 分、入力の短い休みさえとらえられていません — 何かが休みなく入力を送っているのかもしれません。たとえばコントローラーのモーションセンサー（ジャイロ）や、デッドゾーンのないスティック。', '已经 {min} 分钟了，我连一次短暂的输入停顿都没捕捉到——可能有东西在不间断地报告输入，比如手柄的体感传感器（陀螺仪）或者没有死区的摇杆。', 'Уже {min} мин я не поймала ни одной короткой паузы во вводе — возможно, что-то сообщает о нём без перерыва, например датчик движения (гироскоп) геймпада или стик без мёртвой зоны.', 'Llevo {min} minutos sin detectar ni una pausa corta en la entrada — puede que algo la esté enviando sin parar, por ejemplo el sensor de movimiento del mando (giroscopio) o un stick sin zona muerta.', 'Seit {min} Minuten habe ich nicht einmal eine kurze Pause in der Eingabe erwischt — vielleicht sendet etwas ununterbrochen Eingaben, zum Beispiel der Bewegungssensor (Gyro) des Controllers oder ein Stick ohne Deadzone.', 'Depuis {min} minutes, je n’ai pas capté la moindre courte pause dans tes entrées — quelque chose les signale peut-être sans arrêt, par exemple le capteur de mouvement (gyro) de la manette ou un stick sans zone morte.', 'Há {min} minutos não detecto nem uma pausa curta na entrada — talvez algo esteja registrando entrada sem parar, como o sensor de movimento (giroscópio) do controle ou um analógico sem zona morta.')
_tr7('hr.trouble_pad', 'コントローラーでプレイしていますか？ 使っていないならジャイロ（モーションセンサー）をオフにして、スティックに小さなデッドゾーンを設定してください。そうしないとコントローラーが休みなく入力を送り続け、私は声をかけるための休みを見つけられません。', '用手柄玩？如果你不用陀螺仪（体感传感器），就把它关掉，并给摇杆设一个小死区。否则手柄可能会不间断地报告输入，我就找不到可以出声的停顿。', 'Играешь с геймпадом? Выключи в нём гироскоп (датчик движения), если не пользуешься им, и дай стикам небольшую мёртвую зону. Иначе геймпад может сообщать о вводе без перерыва, и я не найду паузу, в которой могла бы подать голос.', '¿Juegas con mando? Desactívale el giroscopio (sensor de movimiento) si no lo usas, y dales a los sticks una pequeña zona muerta. Si no, el mando puede enviar entrada sin parar y no encuentro una pausa en la que avisar.', 'Spielst du mit Controller? Schalte das Gyro (Bewegungssensor) aus, wenn du es nicht nutzt, und gib den Sticks eine kleine Deadzone. Sonst kann der Controller ununterbrochen Eingaben senden, und ich finde keine Pause, in der ich mich melden könnte.', 'Tu joues à la manette ? Désactive son gyro (capteur de mouvement) si tu ne l’utilises pas, et donne aux sticks une petite zone morte. Sinon, la manette peut signaler des entrées sans arrêt, et je ne trouve pas de pause où me manifester.', 'Joga com controle? Desative o giroscópio (sensor de movimento) se não usa, e dê aos analógicos uma pequena zona morta. Senão o controle pode registrar entrada sem parar e eu não encontro uma pausa para avisar.')
_tr7('kamae.snoozed', '静かにしています', '静默中', 'Молчу', 'En silencio', 'Ich schweige', 'Je me tais', 'Em silêncio')
_tr7('kamae.snoozed_sub', '「今はいい」は {until} まで有効です — それまで声はかけませんが、心拍の計測は続けます。{combo} かトレイアイコンのメニューで早めに解除できます。', '“现在不要”持续到 {until}——在那之前我不会出声，但会继续测量心率。用 {combo} 或托盘图标的菜单可以提前结束。', '«Не сейчас» действует до {until} — до тех пор я не подам голос, но пульс продолжаю измерять. Отменить раньше можно сочетанием {combo} или в меню значка в трее.', '«Ahora no» dura hasta las {until} — hasta entonces no aviso, pero sigo midiendo tu pulso. Puedes cancelarlo antes con {combo} o desde el menú del icono de la bandeja.', '„Jetzt nicht“ gilt bis {until} — bis dahin melde ich mich nicht, den Puls messe ich aber weiter. Früher beendest du es mit {combo} oder im Menü des Symbols im Infobereich.', '« Pas maintenant » vaut jusqu’à {until} — d’ici là, je ne me manifeste pas, mais je continue à mesurer ton pouls. Tu l’annules plus tôt avec {combo} ou depuis le menu de l’icône de la zone de notification.', 'O “agora não” vale até {until} — até lá não aviso, mas continuo medindo o seu pulso. Para cancelar antes, use {combo} ou o menu do ícone da bandeja.')
_tr7('settings.preview_sub_sound', '最初の合図の音をゲーム中と同じように鳴らし、その画像を表示します。言葉はなし — 「合図の出し方」でそう選んだからです。', '按游戏中的效果播放第一条提示的声音，并显示它的图片。不带语音——这是你在“我怎样出声”里选的。', 'Проигрывает звук первой подсказки так, как он прозвучит в игре, и показывает её картинку. Без слов — так настроено в «Как я даю о себе знать».', 'Reproduce el sonido del primer aviso tal como sonará en el juego y muestra su imagen. Sin palabras — así lo elegiste en «Cómo aviso».', 'Spielt den Ton des ersten Hinweises so ab, wie er im Spiel klingt, und zeigt sein Bild. Ohne Worte — so hast du es unter „Wie ich mich melde“ gewählt.', 'Joue le son du premier rappel tel qu’il retentira en jeu, et montre son image. Sans paroles — c’est ce que tu as choisi dans « Comment je me manifeste ».', 'Toca o som do primeiro aviso como ele vai soar no jogo e mostra a imagem dele. Sem palavras — foi o que você escolheu em “Como eu aviso”.')
_tr7('settings.preview_sub_visual', '画像だけを選んだので、ゲーム中は何も鳴りません — 合図は表示されるだけです。このボタンは、最初の合図の画像を表示します。', '你只选了图片，所以游戏中不会有任何声音——提示只会显示出来。这个按钮会显示第一条提示的图片。', 'Выбрана только картинка, так что в игре ничего не прозвучит — подсказка лишь покажется. Кнопка покажет картинку первой подсказки.', 'Elegiste solo imagen, así que en el juego no sonará nada — el aviso solo se mostrará. El botón muestra la imagen del primer aviso.', 'Du hast nur ein Bild gewählt, also erklingt im Spiel nichts — der Hinweis wird nur angezeigt. Der Knopf zeigt das Bild des ersten Hinweises.', 'Tu as choisi seulement l’image, donc rien ne retentira en jeu — le rappel s’affiche seulement. Le bouton montre l’image du premier rappel.', 'Você escolheu só imagem, então nada toca no jogo — o aviso só aparece. O botão mostra a imagem do primeiro aviso.')
_tr7('log.preview_no_picture', 'プレビュー：オンになっている合図のどれも、ゲーム中の画像がオンになっていません。このスタイルでは、ゲーム中にまったく合図を出せません。', '预览：没有任何已开启的提示打开了游戏内图片，所以按这种方式，我在游戏中根本不会出现。', 'Предпросмотр: ни у одной включённой подсказки не включена картинка в игре, так что в этом стиле я бы в игре вообще не дала о себе знать.', 'Vista previa: ningún aviso activado tiene activada la imagen en el juego, así que con este estilo no avisaría en el juego en absoluto.', 'Vorschau: Bei keinem eingeschalteten Hinweis ist das Bild im Spiel eingeschaltet, also würde ich mich in diesem Stil im Spiel gar nicht melden.', 'Aperçu : aucun rappel activé n’a son image en jeu activée, donc dans ce style je ne me manifesterais pas du tout en jeu.', 'Prévia: nenhum aviso ativo tem a imagem no jogo ligada, então, neste estilo, eu não apareceria no jogo de jeito nenhum.')
_tr7('session.end.none_snoozed', 'このセッションのうち {min} 分は、あなたの「今はいい」が有効でした — その間は、望みどおり黙っていました。', '本次记录中有 {min} 分钟处于你的“现在不要”状态——那段时间我按你的意思保持了安静。', '{min} мин этой сессии действовало твоё «не сейчас» — тогда я молчала, по твоей же просьбе.', 'Durante {min} min de la sesión estuvo activo tu «ahora no» — entonces me quedé callada, como querías.', '{min} Min der Sitzung galt dein „Jetzt nicht“ — da habe ich geschwiegen, wie du es wolltest.', 'Pendant {min} min de la séance, ton « pas maintenant » était actif — je me suis tue alors, comme tu le voulais.', 'Por {min} min da sessão valeu o seu “agora não” — nesse tempo fiquei calada, como você quis.')
_tr7('tray.close_first', 'トレイで動かし続けるなら、アイコンは時計の横にあります — 見えなければ、^ の矢印の下です。心拍の受信がオンの間、ポート {port} は電話のために開いたまま。私が開始している間（「今日」ページの ▶）は心拍の計測と保存を続けます。あとで完全に終了するには、アイコンを右クリック → 終了。', '如果让我继续在托盘里运行，图标就在时钟旁边——如果看不到，它在 ^ 箭头下面。心率接收开启时，端口 {port} 会一直为手机开着；我处于启动状态时（「今天」页面的 ▶），会继续测量并保存你的心率。之后要彻底退出，请右键点击图标 → 退出。', 'Если оставишь меня работать в трее, значок будет у часов — если его не видно, он под стрелкой ^. Пока включён приём пульса, порт {port} остаётся открытым для телефона; пока я запущена (▶ на странице «Сегодня»), я продолжаю измерять и сохранять пульс. Полностью выключить меня потом можно правым кликом по значку → «Выход».', 'Si me dejas funcionando en la bandeja, mi icono estará junto al reloj: si no lo ves, está bajo la flecha ^. Mientras la recepción del pulso está activada, el puerto {port} sigue abierto para el móvil; mientras estoy iniciada (▶ en la página Hoy), sigo midiendo y guardando tu pulso. Para cerrarme del todo más tarde, clic derecho en el icono → Salir.', 'Lässt du mich im Infobereich weiterlaufen, liegt mein Symbol neben der Uhr — siehst du es nicht, ist es unter dem Pfeil ^. Solange der Pulsempfang an ist, bleibt Port {port} für dein Handy offen; solange ich gestartet bin (▶ auf der Seite Heute), messe und speichere ich deinen Puls weiter. Ganz beendest du mich später mit Rechtsklick aufs Symbol → Beenden.', 'Si tu me laisses tourner dans la zone de notification, mon icône sera près de l’horloge — si tu ne la vois pas, elle est sous la flèche ^. Tant que la réception du pouls est activée, le port {port} reste ouvert pour ton téléphone ; tant que je suis lancée (▶ sur la page Aujourd’hui), je continue de mesurer et d’enregistrer ton pouls. Pour me quitter complètement plus tard : clic droit sur l’icône → Quitter.', 'Se você me deixar rodando na bandeja, meu ícone fica perto do relógio — se não o vir, ele está sob a seta ^. Enquanto a recepção do pulso está ligada, a porta {port} fica aberta para o celular; enquanto estou iniciada (▶ na página Hoje), continuo medindo e salvando o seu pulso. Para me fechar de vez depois, clique com o botão direito no ícone → Sair.')
_tr7('palette.placeholder', 'ページ、プロファイル、合図の名前を入力…', '输入页面、配置文件或提示的名称…', 'Введи название страницы, профиля или подсказки…', 'Escribe el nombre de una página, un perfil o un aviso…', 'Tippe den Namen einer Seite, eines Profils oder eines Hinweises…', 'Tape le nom d’une page, d’un profil ou d’un rappel…', 'Digite o nome de uma página, perfil ou aviso…')
_tr7('palette.replay_intro', 'イントロをもう一度見る', '再看一次介绍', 'Показать вступление снова', 'Ver la introducción de nuevo', 'Intro erneut zeigen', 'Revoir l’intro', 'Mostrar a introdução de novo')
_tr7('palette.profile', 'プロファイル — {name}', '配置文件——{name}', 'Профиль — {name}', 'Perfil — {name}', 'Profil — {name}', 'Profil — {name}', 'Perfil — {name}')
_tr7('palette.cat.help', 'ヘルプ', '帮助', 'Помощь', 'Ayuda', 'Hilfe', 'Aide', 'Ajuda')
_tr7('palette.cat.nav', 'ナビゲーション', '导航', 'Навигация', 'Navegación', 'Navigation', 'Navigation', 'Navegação')
_tr7('palette.cat.sound', 'サウンド', '声音', 'Звук', 'Sonido', 'Ton', 'Son', 'Som')
_tr7('palette.cat.app', 'アプリ', '应用', 'Приложение', 'App', 'App', 'App', 'App')
_tr7('palette.cat.profiles', 'プロファイル', '配置文件', 'Профили', 'Perfiles', 'Profile', 'Profils', 'Perfis')
_tr7('edge.after_game', '合図の音声は、見守りを止めたときに準備します。', '你停止关注后，我会准备提示的语音。', 'Голос подсказок подготовлю, когда ты остановишь наблюдение.', 'Prepararé la voz de los avisos cuando detengas la observación.', 'Die Stimme der Hinweise bereite ich vor, wenn du die Beobachtung stoppst.', 'Je préparerai la voix des rappels quand tu arrêteras l’observation.', 'Vou preparar a voz dos avisos quando você parar de observar.')
_tr7('ob.cue.online_note', '自然な音声はオンラインです：合図の文面（心拍は決して送りません）を、音声に変換するために Microsoft に送ります。Windows の音声は何も送りません — 「設定」→「サウンド」で切り替えられます。', '自然语音需要联网：提示的文字（绝不包括心率）会发送给 Microsoft 的服务转换成语音。Windows 语音不会发送任何东西——可以在“设置 → 声音”里切换。', 'Естественный голос работает онлайн: текст подсказок (но никогда не пульс) отправляется сервису Microsoft для преобразования в речь. Голос Windows ничего не отправляет — переключиться на него можно в «Настройки → Звук».', 'La voz natural funciona en línea: el texto de los avisos (nunca tu pulso) se envía al servicio de Microsoft para convertirlo en voz. La voz de Windows no envía nada — puedes cambiar a ella en Ajustes → Sonido.', 'Die natürliche Stimme ist online: Der Text der Hinweise (nie dein Puls) geht an Microsoft und wird dort in Sprache umgewandelt. Die Windows-Stimme schickt nichts — du wechselst zu ihr unter Einstellungen → Ton.', 'La voix naturelle passe par internet : le texte des rappels (jamais ton pouls) est envoyé au service Microsoft pour être converti en parole. La voix Windows n’envoie rien — tu peux la choisir dans Paramètres → Son.', 'A voz natural é online: o texto dos avisos (nunca o seu pulso) é enviado ao serviço da Microsoft para ser convertido em fala. A voz do Windows não envia nada — você pode trocar para ela em Configurações → Som.')
_tr7('settings.language_note', 'アプリはスロバキア語で書かれています。ほかの言語は AI の助けを借りた翻訳で、まだネイティブスピーカーの確認を受けていません — 間違いを見つけたら教えてください。', '本应用以斯洛伐克语编写。其他语言是借助 AI 翻译的，尚未经过母语者校对——如果你发现错误，请告诉我。', 'Приложение написано на словацком. Остальные языки — переводы с помощью ИИ, и носитель языка их ещё не проверял; если заметишь ошибку, дай знать.', 'La app está escrita en eslovaco. Los demás idiomas son traducciones hechas con ayuda de IA que todavía no ha revisado ningún hablante nativo — si ves un error, avísame.', 'Die App ist auf Slowakisch geschrieben. Die anderen Sprachen sind KI-gestützte Übersetzungen, die noch nicht von Muttersprachlern geprüft wurden — wenn du einen Fehler siehst, sag Bescheid.', 'L’app est écrite en slovaque. Les autres langues sont des traductions faites avec l’aide de l’IA, pas encore relues par un locuteur natif — si tu vois une erreur, dis-le-moi.', 'O app foi escrito em eslovaco. Os outros idiomas são traduções feitas com ajuda de IA e ainda não foram revisados por um falante nativo — se encontrar um erro, avise.')


# --- 0.2.1: "not now" also in the tray icon menu --------------------------
# When another app holds the shortcut (Ctrl+Alt+Z), `RegisterHotKey`
# fails and cues could only be silenced by stopping listening - which
# stops measuring too. Since 0.2.1 "not now" is also an item in the tray
# icon menu (`setup_tray`) and the journal line on a shortcut failure
# sends the player there (`start_snooze_hotkey`). The sentence about the
# failure promises only what always applies ("it does not stop
# listening"), not measuring - snoozing can be turned on even in a
# stopped app, and then nothing is measured (same as
# `log.snooze_started`). SK/EN by hand, 7 languages right under them,
# Czech and Bulgarian in `i18n_cs_bg.py`.
STRINGS.update({
    'tray.snooze': _sk_en('Teraz nie ({minutes} min)', 'Not now ({minutes} min)'),
    'log.hotkey_failed_tray': _sk_en(
        'Skratku {combo} drží iná aplikácia, takže nepôjde. „Teraz nie“ nájdeš aj v ponuke ikony v lište (pravý klik) — sledovanie to nezastaví.',
        'Another app holds {combo}, so the shortcut won’t work. “Not now” is also in the tray icon’s menu (right-click) — it doesn’t stop watching.'),
})
_tr7('tray.snooze', '今はいい（{minutes} 分）', '现在不要（{minutes} 分钟）', 'Не сейчас ({minutes} мин)', 'Ahora no ({minutes} min)', 'Jetzt nicht ({minutes} Min.)', 'Pas maintenant ({minutes} min)', 'Agora não ({minutes} min)')
_tr7('log.hotkey_failed_tray', '別のアプリが {combo} を使っているため、このショートカットは使えません。「今はいい」はトレイアイコンのメニュー（右クリック）にもあります — 見守りは止まりません。', '{combo} 被另一个应用占用，所以这个快捷键用不了。“现在不要”也在托盘图标的菜单里（右键）——它不会停止关注。', 'Сочетание {combo} занято другим приложением, поэтому оно не сработает. «Не сейчас» есть и в меню значка в трее (правый клик) — наблюдение это не останавливает.', 'Otra app tiene {combo}, así que el atajo no funcionará. «Ahora no» también está en el menú del icono de la bandeja (clic derecho): no detiene la observación.', 'Eine andere App belegt {combo}, daher funktioniert das Kürzel nicht. „Jetzt nicht“ findest du auch im Menü des Symbols im Infobereich (Rechtsklick) — die Beobachtung stoppt es nicht.', 'Une autre app occupe {combo}, donc le raccourci ne marchera pas. « Pas maintenant » est aussi dans le menu de l’icône de la zone de notification (clic droit) — ça n’arrête pas l’observation.', 'Outro app está usando {combo}, então o atalho não vai funcionar. “Agora não” também está no menu do ícone da bandeja (clique direito) — isso não para a observação.')


# --- 0.2.1: UDP on the heart rate port did not open --------------------------
# While `heart_rate._udp_loop` silently ended on a bind failure, an app
# sending only UDP/OSC (iPhone) had no way to get through and the player
# did not see why. TCP (apps for OBS) meanwhile keeps running - so the
# journal line also says what works, and the label by the switch says
# "TCP only" (`_hr_status_display`), not "busy port" as with TCP. SK/EN
# by hand, 7 languages under them, cs/bg in `i18n_cs_bg.py`.
STRINGS.update({
    'log.hr_udp_busy': _sk_en(
        'UDP port {port} drží iný program, takže tep cez OSC (napr. z iPhonu cez PulseOSC) nepríde. Appka pre Android (HeartRateOnStream) funguje ďalej. Zavri ten program a „Prijímať tep z telefónu“ vypni a zapni.',
        'Another program holds UDP port {port}, so heart rate over OSC (e.g. from an iPhone via PulseOSC) won’t arrive. The Android app (HeartRateOnStream) keeps working. Close that program, then turn “Receive heart rate from the phone” off and on.'),
    'log.hr_udp_error': _sk_en(
        'UDP na porte {port} sa nepodarilo otvoriť ({err}), takže tep cez OSC (napr. z iPhonu cez PulseOSC) nepríde. Appka pre Android (HeartRateOnStream) funguje ďalej.',
        'Couldn’t open UDP on port {port} ({err}), so heart rate over OSC (e.g. from an iPhone via PulseOSC) won’t arrive. The Android app (HeartRateOnStream) keeps working.'),
    'settings.hr_status_udp_off': _sk_en(
        'Android sa pripojí, iPhone (PulseOSC) nie',
        'Android can connect, iPhone (PulseOSC) can’t'),
})
_tr7('log.hr_udp_busy', 'UDP ポート {port} は別のプログラムが使用中のため、OSC の心拍（例：iPhone の PulseOSC から）は届きません。Android 用アプリ（HeartRateOnStream）はそのまま動きます。そのプログラムを閉じてから、「電話から心拍を受け取る」をオフにして再びオンにしてください。', 'UDP 端口 {port} 被其他程序占用，因此通过 OSC 发送的心率（例如 iPhone 上的 PulseOSC）收不到。Android 应用（HeartRateOnStream）照常工作。关闭那个程序，然后把“接收手机发来的心率”关掉再打开。', 'UDP-порт {port} занят другой программой, поэтому пульс по OSC (например, с iPhone через PulseOSC) не придёт. Приложение для Android (HeartRateOnStream) работает дальше. Закрой ту программу, затем выключи и снова включи «Принимать пульс с телефона».', 'Otro programa tiene el puerto UDP {port}, así que el pulso por OSC (p. ej., desde un iPhone con PulseOSC) no llegará. La app para Android (HeartRateOnStream) sigue funcionando. Cierra ese programa y luego desactiva y vuelve a activar «Recibir el pulso del móvil».', 'Ein anderes Programm belegt den UDP-Port {port}, daher kommt der Puls über OSC (z. B. vom iPhone mit PulseOSC) nicht an. Die Android-App (HeartRateOnStream) funktioniert weiter. Schließe dieses Programm und schalte dann „Puls vom Handy empfangen“ aus und wieder ein.', 'Un autre programme occupe le port UDP {port}, donc le pouls via OSC (par ex. depuis un iPhone avec PulseOSC) n’arrivera pas. L’app Android (HeartRateOnStream) continue de fonctionner. Ferme ce programme, puis désactive et réactive « Recevoir le pouls du téléphone ».', 'Outro programa está usando a porta UDP {port}, então o pulso via OSC (por ex., de um iPhone com PulseOSC) não vai chegar. O app para Android (HeartRateOnStream) continua funcionando. Feche esse programa e depois desligue e ligue de novo “Receber o pulso do celular”.')
_tr7('log.hr_udp_error', 'ポート {port} の UDP を開けませんでした（{err}）。OSC の心拍（例：iPhone の PulseOSC から）は届きません。Android 用アプリ（HeartRateOnStream）はそのまま動きます。', '无法打开端口 {port} 上的 UDP（{err}），因此通过 OSC 发送的心率（例如 iPhone 上的 PulseOSC）收不到。Android 应用（HeartRateOnStream）照常工作。', 'Не удалось открыть UDP на порту {port} ({err}), поэтому пульс по OSC (например, с iPhone через PulseOSC) не придёт. Приложение для Android (HeartRateOnStream) работает дальше.', 'No se pudo abrir UDP en el puerto {port} ({err}), así que el pulso por OSC (p. ej., desde un iPhone con PulseOSC) no llegará. La app para Android (HeartRateOnStream) sigue funcionando.', 'UDP auf Port {port} konnte nicht geöffnet werden ({err}), daher kommt der Puls über OSC (z. B. vom iPhone mit PulseOSC) nicht an. Die Android-App (HeartRateOnStream) funktioniert weiter.', 'Impossible d’ouvrir l’UDP sur le port {port} ({err}), donc le pouls via OSC (par ex. depuis un iPhone avec PulseOSC) n’arrivera pas. L’app Android (HeartRateOnStream) continue de fonctionner.', 'Não foi possível abrir o UDP na porta {port} ({err}), então o pulso via OSC (por ex., de um iPhone com PulseOSC) não vai chegar. O app para Android (HeartRateOnStream) continua funcionando.')
_tr7('settings.hr_status_udp_off', 'Android は接続できます。iPhone（PulseOSC）はできません', 'Android 可以连接，iPhone（PulseOSC）不行', 'Android подключится, iPhone (PulseOSC) — нет', 'Android se conecta; iPhone (PulseOSC), no', 'Android kann sich verbinden, iPhone (PulseOSC) nicht', 'Android peut se connecter, l’iPhone (PulseOSC) non', 'O Android conecta, o iPhone (PulseOSC) não')


# --- 0.3: two different heart rates in one source ----------------------------
# The app on the watch can write two heart-rate streams into one OBS
# source at once and the number then jumps (`heart_rate.dva_rady_v_okne`).
# A journal line once per run (source name, no values) and a text by the
# switch after the heart rate number (`_hr_status_display`). The sentence
# also says what the app does about it: it smooths the number on screen,
# the measurement takes every value - so the setting on the watch needs
# fixing. SK/EN by hand, 7 languages under them, cs/bg in
# `i18n_cs_bg.py`.
STRINGS.update({
    'log.hr_two_series': _sk_en(
        'Appka na hodinkách posiela do zdroja „{source}“ dva rôzne tepy, takže '
        'hodnoty preskakujú medzi nimi. Číslo na obrazovke je vyhladené, no '
        'meranie berie každú hodnotu: v appke na hodinkách nechaj do tohto '
        'zdroja zapisovať len živý tep.',
        'The watch app is sending two different heart rates into the source '
        '“{source}”, so the readings jump between them. The number on screen '
        'is smoothed, but measuring uses every reading: in the watch app, let '
        'only the live heart rate write into this source.'),
    'settings.hr_status_two_series': _sk_en(
        'Dva rôzne tepy v jednom zdroji — skontroluj appku na hodinkách',
        'Two different heart rates in one source — check the watch app'),
})
_tr7('log.hr_two_series', '時計アプリがソース「{source}」に異なる心拍を2つ送っているため、値がその間を行き来しています。画面の数値はなめらかにしていますが、計測にはすべての値を使います。時計アプリで、このソースにはリアルタイムの心拍だけを書き込むようにしてください。', '手表应用正在向来源“{source}”发送两个不同的心率，所以数值在两者之间来回跳。屏幕上的数字做了平滑，但测量会用到每一个读数：请在手表应用里只让实时心率写入这个来源。', 'Приложение на часах отправляет в источник «{source}» два разных пульса, поэтому значения прыгают между ними. Число на экране сглажено, но измерение учитывает каждое значение: в приложении на часах оставь для этого источника только живой пульс.', 'La app del reloj envía dos pulsos distintos a la fuente «{source}», así que los valores saltan entre ellos. El número en pantalla está suavizado, pero la medición usa cada lectura: en la app del reloj, deja que en esta fuente solo escriba el pulso en vivo.', 'Die Uhr-App schickt zwei verschiedene Pulswerte in die Quelle „{source}“, deshalb springen die Werte zwischen ihnen hin und her. Die Zahl auf dem Bildschirm ist geglättet, die Messung nutzt aber jeden Wert: Lass in der Uhr-App nur den Live-Puls in diese Quelle schreiben.', 'L’app de la montre envoie deux pouls différents dans la source « {source} », donc les valeurs sautent de l’un à l’autre. Le chiffre à l’écran est lissé, mais la mesure utilise chaque valeur : dans l’app de la montre, laisse seulement le pouls en direct écrire dans cette source.', 'O app do relógio está enviando dois pulsos diferentes para a fonte “{source}”, então os valores pulam entre eles. O número na tela é suavizado, mas a medição usa cada leitura: no app do relógio, deixe só o pulso ao vivo escrever nessa fonte.')
_tr7('settings.hr_status_two_series', '1つのソースに異なる心拍が2つ — 時計アプリを確認して', '一个来源里有两个不同的心率——请检查手表应用', 'Два разных пульса в одном источнике — проверь приложение на часах', 'Dos pulsos distintos en una fuente — revisa la app del reloj', 'Zwei verschiedene Pulswerte in einer Quelle — prüf die Uhr-App', 'Deux pouls différents dans une source — vérifie l’app de la montre', 'Dois pulsos diferentes em uma fonte — confira o app do relógio')


# --- 0.3: one vocabulary and shorter texts (UX audit, part 3) ------------
# The main switch is "sledovat" (en "watching"), the heart rate receiver
# "prijimat tep" (en "heart-rate receiving") and what the app sends is a
# "pripomienka" (en "cue"). Before, one thing had five names and
# "odpocuvat" in Slovak means to spy - for an app that reads the timing
# of inputs, the worst possible word.
# New keys and added translations for `_sk_en` keys that did not have
# them yet.
STRINGS.update({
    'session.end.cues_silent': {
        'sk': 'Ozvala som sa {n}×, z toho {silent}× schválne len obrázkom — aby bolo s čím porovnať.',
        'en': 'I spoke up {n}×; {silent} of those were picture-only on purpose, for comparison.',
        'ja': '{n} 回合図を出しました。そのうち {silent} 回は比較のため、わざと画像だけにしました。',
        'zh': '我提醒了你 {n} 次，其中 {silent} 次故意只显示图片，用来做对比。',
        'ru': 'Я подала знак {n}×, из них {silent}× нарочно только картинкой — чтобы было с чем сравнить.',
        'es': 'Te he avisado {n}×; {silent} de ellas, a propósito solo con imagen, para poder comparar.',
        'de': 'Ich habe mich {n}× gemeldet, davon {silent}× absichtlich nur mit Bild — zum Vergleich.',
        'fr': 'Je me suis manifestée {n}×, dont {silent}× volontairement par une image seule — pour comparer.',
        'pt': 'Avisei {n}×; {silent} delas foram de propósito só com imagem, para comparar.',
    },
    'cue_style.voice': {
        'sk': 'Hlas, zvuk a obrázok',
        'en': 'Voice, sound and picture',
        'ja': '音声・効果音・画像',
        'zh': '语音、音效和图片',
        'ru': 'Голос, звук и картинка',
        'es': 'Voz, sonido e imagen',
        'de': 'Stimme, Ton und Bild',
        'fr': 'Voix, son et image',
        'pt': 'Voz, som e imagem',
    },
    'cue_style.sound': {
        'sk': 'Zvuk a obrázok',
        'en': 'Sound and picture',
        'ja': '効果音と画像',
        'zh': '音效和图片',
        'ru': 'Звук и картинка',
        'es': 'Sonido e imagen',
        'de': 'Ton und Bild',
        'fr': 'Son et image',
        'pt': 'Som e imagem',
    },
    'cue_style.visual': {
        'sk': 'Len obrázok',
        'en': 'Picture only',
        'ja': '画像だけ',
        'zh': '只用图片',
        'ru': 'Только картинка',
        'es': 'Solo imagen',
        'de': 'Nur Bild',
        'fr': 'Image seulement',
        'pt': 'Só imagem',
    },
    'tray.start': {
        'sk': 'Spustiť sledovanie',
        'en': 'Start watching',
        'ja': '見守りを開始',
        'zh': '开始关注',
        'ru': 'Начать наблюдение',
        'es': 'Empezar a observar',
        'de': 'Beobachtung starten',
        'fr': 'Lancer l’observation',
        'pt': 'Começar a observar',
    },
    'tray.stop': {
        'sk': 'Zastaviť sledovanie',
        'en': 'Stop watching',
        'ja': '見守りを停止',
        'zh': '停止关注',
        'ru': 'Остановить наблюдение',
        'es': 'Dejar de observar',
        'de': 'Beobachtung stoppen',
        'fr': 'Arrêter l’observation',
        'pt': 'Parar de observar',
    },
})
_tr7('history.col_hrr', '回復', '恢复', 'Восст.', 'Recup.', 'Erholung', 'Récup.', 'Recup.')
_tr7('history.col_hrpi', '持続', '持续', 'Устойч.', 'Persist.', 'Persist.', 'Persist.', 'Persist.')
_tr7('history.detail_hrpi', '持続', '持续', 'Устойчивость', 'Persistencia', 'Persistenz', 'Persistance', 'Persistência')
_tr7('history.export_col.hrpi', '心拍の持続（HRPI）', '心率持续（HRPI）', 'Устойчивость пульса (HRPI)', 'Persistencia del pulso (HRPI)', 'Puls-Persistenz (HRPI)', 'Persistance du pouls (HRPI)', 'Persistência do pulso (HRPI)')


# --- 0.3: "Update voice" (a newer edge-tts on a click) -----------------------
# The author's decision (15. 11. 2026): when Microsoft refuses the
# edge-tts that is in Zanshin, the player downloads a newer one
# themselves with a button in Settings → Sound (under Voice source) or
# via Ctrl+K - only on a click and never while watching
# (`AudioMixin.aktualizuj_hlas`, core `hlas_kniznica.py`). The status
# under Voice source has a mark like the other voice states (⟳ / ✓ / !),
# the journal line is without it. Where only a new Zanshin fixes the
# voice, the sentence points to the official GitHub (Releases) without a
# URL - the link is the button next to it (`edge.update.releases_btn`,
# the app adds "↗" to it). The technical reason goes only to app.log.
# SK/EN by hand, 7 languages under them, cs/bg in `i18n_cs_bg.py`.
STRINGS.update({
    'edge.update.btn': _sk_en('Aktualizovať hlas', 'Update voice'),
    'edge.update.releases_btn': _sk_en('Nový Zanshin na GitHube', 'New Zanshin on GitHub'),
    'edge.update.running': _sk_en(
        '⟳ aktualizujem hlas — hľadám novšiu verziu, sťahujem ju a skúšam jedným slovom…',
        '⟳ updating the voice — looking for a newer version, downloading it and testing it '
        'with one word…'),
    'edge.update.after_watching': _sk_en(
        'Hlas sa dá aktualizovať, keď zastavíš sledovanie.',
        'You can update the voice once you stop watching.'),
    'edge.update.up_to_date': _sk_en('✓ hlas je aktuálny (edge-tts {version})',
                                     '✓ the voice is up to date (edge-tts {version})'),
    'edge.update.updated': _sk_en('✓ hlas aktualizovaný na edge-tts {version} — funguje',
                                  '✓ voice updated to edge-tts {version} — it works'),
    'edge.update.refused_still': _sk_en(
        '! Microsoft odmieta aj najnovšiu verziu hlasu — stiahni si nový Zanshin '
        'z oficiálneho GitHubu (Releases).',
        '! Microsoft refuses even the newest voice version — get the new Zanshin from the '
        'official GitHub (Releases).'),
    'edge.update.offline': _sk_en(
        '! hlas sa teraz nedá aktualizovať — skontroluj internet. Nič sa nezmenilo.',
        '! the voice can’t be updated right now — check your internet connection. '
        'Nothing changed.'),
    'edge.update.incompatible': _sk_en(
        '! táto aktualizácia hlasu potrebuje novší Zanshin — nájdeš ho na oficiálnom '
        'GitHube (Releases). Doterajší hlas ostáva.',
        '! this voice update needs a newer Zanshin — get it from the official GitHub '
        '(Releases). The current voice stays.'),
    'edge.update.verify_failed': _sk_en(
        '! stiahnutý hlas neprešiel kontrolou, tak som ho nepoužila — doterajší ostáva. '
        'Skús to neskôr.',
        '! the downloaded voice didn’t pass the check, so I didn’t use it — the current one '
        'stays. Try later.'),
    'edge.update.error': _sk_en(
        '! hlas sa nepodarilo aktualizovať — doterajší ostáva. Skús to neskôr.',
        '! the voice couldn’t be updated — the current one stays. Try later.'),
    'log.edge_update.up_to_date': _sk_en(
        'Hlas je aktuálny: edge-tts {version} je najnovší a skúšobné slovo prešlo.',
        'The voice is up to date: edge-tts {version} is the newest, and the test word '
        'went through.'),
    'log.edge_update.updated': _sk_en(
        'Hlas som aktualizovala na edge-tts {version} — skúšobné slovo prešlo a pripomienky '
        'odteraz hovoria ním.',
        'I updated the voice to edge-tts {version} — the test word went through, and cues '
        'use it from now on.'),
    'log.edge_update.refused_still': _sk_en(
        'Microsoft odmieta aj najnovší edge-tts ({version}). Pozri nový Zanshin na '
        'oficiálnom GitHube (Releases); dovtedy zvyšok povie hlas z Windows.',
        'Microsoft refuses even the newest edge-tts ({version}). Look for a new Zanshin on '
        'the official GitHub (Releases); until then the Windows voice covers the rest.'),
    'log.edge_update.offline': _sk_en(
        'Hlas sa nedal aktualizovať — služba je teraz nedostupná (internet alebo DNS). Nič '
        'sa nezmenilo; skús to neskôr.',
        'Couldn’t update the voice — the service can’t be reached right now (internet or '
        'DNS). Nothing changed; try later.'),
    'log.edge_update.incompatible': _sk_en(
        'Najnovší edge-tts potrebuje novší Zanshin — nájdeš ho na oficiálnom GitHube '
        '(Releases). Doterajší hlas ostáva.',
        'The newest edge-tts needs a newer Zanshin — get it from the official GitHub '
        '(Releases). The current voice stays.'),
    'log.edge_update.verify_failed': _sk_en(
        'Stiahnutý hlas neprešiel kontrolou, tak som ho zahodila — doterajší ostáva. '
        'Podrobnosti sú v app.log.',
        'The downloaded voice didn’t pass the check, so I discarded it — the current one '
        'stays. Details are in app.log.'),
    'log.edge_update.error': _sk_en(
        'Hlas sa nepodarilo aktualizovať — doterajší ostáva. Podrobnosti sú v app.log.',
        'Couldn’t update the voice — the current one stays. Details are in app.log.'),
    'log.edge_update.cancelled': _sk_en(
        'Aktualizáciu hlasu som prerušila (začalo sa sledovanie alebo je zvolený hlas '
        'z Windows) — nič sa nezmenilo.',
        'I stopped the voice update (watching started, or the Windows voice was chosen) — '
        'nothing changed.'),
})
_tr7('edge.update.btn', '音声を更新', '更新语音', 'Обновить голос', 'Actualizar la voz', 'Stimme aktualisieren', 'Mettre à jour la voix', 'Atualizar a voz')
_tr7('edge.update.releases_btn', 'GitHub で新しい Zanshin を入手', '在 GitHub 获取新版 Zanshin', 'Новый Zanshin на GitHub', 'Nuevo Zanshin en GitHub', 'Neues Zanshin auf GitHub', 'Nouveau Zanshin sur GitHub', 'Novo Zanshin no GitHub')
_tr7('edge.update.running', '⟳ 音声を更新中 — 新しい版を探し、ダウンロードして、ひと言で試しています…', '⟳ 正在更新语音——查找新版本、下载，并用一个词试听…', '⟳ обновляю голос — ищу новую версию, скачиваю её и проверяю одним словом…', '⟳ actualizando la voz: busco una versión más nueva, la descargo y la pruebo con una palabra…', '⟳ aktualisiere die Stimme — suche eine neuere Version, lade sie herunter und teste sie mit einem Wort…', '⟳ je mets à jour la voix — je cherche une version plus récente, je la télécharge et je la teste avec un mot…', '⟳ atualizando a voz — procuro uma versão mais nova, baixo e testo com uma palavra…')
_tr7('edge.update.after_watching', '音声の更新は、見守りを止めてからできます。', '你停止关注后才能更新语音。', 'Обновить голос можно, когда ты остановишь наблюдение.', 'Podrás actualizar la voz cuando detengas la observación.', 'Die Stimme lässt sich aktualisieren, wenn du die Beobachtung stoppst.', 'Tu pourras mettre à jour la voix quand tu arrêteras l’observation.', 'Dá para atualizar a voz quando você parar de observar.')
_tr7('edge.update.up_to_date', '✓ 音声は最新です（edge-tts {version}）', '✓ 语音已是最新（edge-tts {version}）', '✓ голос актуален (edge-tts {version})', '✓ la voz está al día (edge-tts {version})', '✓ die Stimme ist aktuell (edge-tts {version})', '✓ la voix est à jour (edge-tts {version})', '✓ a voz está atualizada (edge-tts {version})')
_tr7('edge.update.updated', '✓ 音声を edge-tts {version} に更新しました — 動作しています', '✓ 语音已更新到 edge-tts {version}——可以正常使用', '✓ голос обновлён до edge-tts {version} — работает', '✓ voz actualizada a edge-tts {version}: funciona', '✓ Stimme auf edge-tts {version} aktualisiert — sie funktioniert', '✓ voix mise à jour vers edge-tts {version} — elle fonctionne', '✓ voz atualizada para edge-tts {version} — funciona')
_tr7('edge.update.refused_still', '! Microsoft は最新版の音声も拒否しています — 新しい Zanshin を公式の GitHub（Releases）から入手してください。', '! 微软连最新版本的语音也拒绝了——请从官方 GitHub（Releases）获取新版 Zanshin。', '! Microsoft отклоняет даже самую новую версию голоса — возьми новый Zanshin на официальном GitHub (Releases).', '! Microsoft rechaza incluso la versión más nueva de la voz: consigue el nuevo Zanshin en el GitHub oficial (Releases).', '! Microsoft lehnt selbst die neueste Version der Stimme ab — hol dir das neue Zanshin vom offiziellen GitHub (Releases).', '! Microsoft refuse même la version la plus récente de la voix — prends le nouveau Zanshin sur le GitHub officiel (Releases).', '! A Microsoft recusa até a versão mais nova da voz — pegue o novo Zanshin no GitHub oficial (Releases).')
_tr7('edge.update.offline', '! いまは音声を更新できません — インターネットを確認して。何も変わっていません。', '! 现在无法更新语音——请检查网络。什么都没有改变。', '! сейчас голос не обновить — проверь интернет. Ничего не изменилось.', '! ahora no se puede actualizar la voz: revisa tu conexión a internet. No ha cambiado nada.', '! die Stimme lässt sich gerade nicht aktualisieren — prüf deine Internetverbindung. Nichts wurde geändert.', '! impossible de mettre à jour la voix pour l’instant — vérifie ta connexion internet. Rien n’a changé.', '! agora não dá para atualizar a voz — confira a sua internet. Nada mudou.')
_tr7('edge.update.incompatible', '! この音声の更新には新しい Zanshin が必要です — 公式の GitHub（Releases）から入手してください。いまの音声はそのままです。', '! 这次语音更新需要更新版的 Zanshin——请从官方 GitHub（Releases）获取。当前的语音保持不变。', '! для этого обновления голоса нужен более новый Zanshin — возьми его на официальном GitHub (Releases). Текущий голос остаётся.', '! esta actualización de la voz necesita un Zanshin más nuevo: consíguelo en el GitHub oficial (Releases). La voz actual se queda.', '! dieses Update der Stimme braucht ein neueres Zanshin — hol es dir vom offiziellen GitHub (Releases). Die bisherige Stimme bleibt.', '! cette mise à jour de la voix demande un Zanshin plus récent — prends-le sur le GitHub officiel (Releases). La voix actuelle reste.', '! esta atualização da voz precisa de um Zanshin mais novo — pegue-o no GitHub oficial (Releases). A voz atual continua.')
_tr7('edge.update.verify_failed', '! ダウンロードした音声がチェックを通らなかったので、使いませんでした — いまの音声はそのままです。あとで試して。', '! 下载的语音没有通过检查，所以我没有使用它——当前的语音保持不变。请稍后再试。', '! скачанный голос не прошёл проверку, поэтому я его не использовала — текущий остаётся. Попробуй позже.', '! la voz descargada no pasó la comprobación, así que no la usé: la actual se queda. Inténtalo más tarde.', '! die heruntergeladene Stimme hat die Prüfung nicht bestanden, deshalb habe ich sie nicht verwendet — die bisherige bleibt. Versuch es später.', '! la voix téléchargée n’a pas passé la vérification, je ne l’ai donc pas utilisée — la voix actuelle reste. Réessaie plus tard.', '! a voz baixada não passou na verificação, então não a usei — a atual continua. Tente mais tarde.')
_tr7('edge.update.error', '! 音声を更新できませんでした — いまの音声はそのままです。あとで試して。', '! 未能更新语音——当前的语音保持不变。请稍后再试。', '! голос не удалось обновить — текущий остаётся. Попробуй позже.', '! no se pudo actualizar la voz: la actual se queda. Inténtalo más tarde.', '! die Stimme ließ sich nicht aktualisieren — die bisherige bleibt. Versuch es später.', '! impossible de mettre à jour la voix — la voix actuelle reste. Réessaie plus tard.', '! não foi possível atualizar a voz — a atual continua. Tente mais tarde.')
_tr7('log.edge_update.up_to_date', '音声は最新です：edge-tts {version} が最新版で、試しのひと言も通りました。', '语音已是最新：edge-tts {version} 是最新版本，试听的词也顺利通过。', 'Голос актуален: edge-tts {version} — самая новая версия, и пробное слово прошло.', 'La voz está al día: edge-tts {version} es la más nueva y la palabra de prueba funcionó.', 'Die Stimme ist aktuell: edge-tts {version} ist die neueste Version, und das Testwort ging durch.', 'La voix est à jour : edge-tts {version} est la plus récente, et le mot de test est passé.', 'A voz está atualizada: edge-tts {version} é a mais nova, e a palavra de teste funcionou.')
_tr7('log.edge_update.updated', '音声を edge-tts {version} に更新しました — 試しのひと言が通ったので、これからは合図もこの版で話します。', '我把语音更新到了 edge-tts {version}——试听的词顺利通过，从现在起提示都用它来说。', 'Я обновила голос до edge-tts {version} — пробное слово прошло, и подсказки теперь звучат с ним.', 'He actualizado la voz a edge-tts {version}: la palabra de prueba funcionó y los avisos la usan desde ahora.', 'Ich habe die Stimme auf edge-tts {version} aktualisiert — das Testwort ging durch, und die Hinweise nutzen sie ab jetzt.', 'J’ai mis à jour la voix vers edge-tts {version} — le mot de test est passé, et les rappels l’utilisent désormais.', 'Atualizei a voz para edge-tts {version} — a palavra de teste funcionou, e os avisos a usam a partir de agora.')
_tr7('log.edge_update.refused_still', 'Microsoft は最新の edge-tts（{version}）も拒否しています。公式の GitHub（Releases）で新しい Zanshin を探してください。それまでは残りを Windows の音声が話します。', '微软连最新的 edge-tts（{version}）也拒绝了。请到官方 GitHub（Releases）查看新版 Zanshin；在那之前，其余的由 Windows 语音来说。', 'Microsoft отклоняет даже самый новый edge-tts ({version}). Поищи новый Zanshin на официальном GitHub (Releases); до тех пор остальное скажет голос Windows.', 'Microsoft rechaza incluso el edge-tts más nuevo ({version}). Busca un Zanshin nuevo en el GitHub oficial (Releases); hasta entonces, el resto lo dice la voz de Windows.', 'Microsoft lehnt selbst das neueste edge-tts ({version}) ab. Schau auf dem offiziellen GitHub (Releases) nach einem neuen Zanshin; bis dahin spricht die Windows-Stimme den Rest.', 'Microsoft refuse même le edge-tts le plus récent ({version}). Cherche un nouveau Zanshin sur le GitHub officiel (Releases) ; d’ici là, la voix de Windows dit le reste.', 'A Microsoft recusa até o edge-tts mais novo ({version}). Procure um Zanshin novo no GitHub oficial (Releases); até lá, o resto fica com a voz do Windows.')
_tr7('log.edge_update.offline', '音声を更新できませんでした — いまはサービスに接続できません（インターネットか DNS）。何も変わっていません。あとで試して。', '未能更新语音——现在连不上服务（网络或 DNS）。什么都没有改变；请稍后再试。', 'Голос не удалось обновить — сервис сейчас недоступен (интернет или DNS). Ничего не изменилось; попробуй позже.', 'No pude actualizar la voz: ahora no se puede llegar al servicio (internet o DNS). No ha cambiado nada; inténtalo más tarde.', 'Die Stimme ließ sich nicht aktualisieren — der Dienst ist gerade nicht erreichbar (Internet oder DNS). Nichts wurde geändert; versuch es später.', 'Je n’ai pas pu mettre à jour la voix — le service est injoignable pour l’instant (internet ou DNS). Rien n’a changé ; réessaie plus tard.', 'Não consegui atualizar a voz — o serviço não está acessível agora (internet ou DNS). Nada mudou; tente mais tarde.')
_tr7('log.edge_update.incompatible', '最新の edge-tts には新しい Zanshin が必要です — 公式の GitHub（Releases）から入手してください。いまの音声はそのままです。', '最新的 edge-tts 需要更新版的 Zanshin——请从官方 GitHub（Releases）获取。当前的语音保持不变。', 'Самому новому edge-tts нужен более новый Zanshin — возьми его на официальном GitHub (Releases). Текущий голос остаётся.', 'El edge-tts más nuevo necesita un Zanshin más nuevo: consíguelo en el GitHub oficial (Releases). La voz actual se queda.', 'Das neueste edge-tts braucht ein neueres Zanshin — hol es dir vom offiziellen GitHub (Releases). Die bisherige Stimme bleibt.', 'Le edge-tts le plus récent demande un Zanshin plus récent — prends-le sur le GitHub officiel (Releases). La voix actuelle reste.', 'O edge-tts mais novo precisa de um Zanshin mais novo — pegue-o no GitHub oficial (Releases). A voz atual continua.')
_tr7('log.edge_update.verify_failed', 'ダウンロードした音声がチェックを通らなかったので、破棄しました — いまの音声はそのままです。詳しくは app.log にあります。', '下载的语音没有通过检查，所以我把它丢弃了——当前的语音保持不变。详情见 app.log。', 'Скачанный голос не прошёл проверку, поэтому я его удалила — текущий остаётся. Подробности в app.log.', 'La voz descargada no pasó la comprobación, así que la descarté: la actual se queda. Los detalles están en app.log.', 'Die heruntergeladene Stimme hat die Prüfung nicht bestanden, deshalb habe ich sie verworfen — die bisherige bleibt. Details stehen in app.log.', 'La voix téléchargée n’a pas passé la vérification, je l’ai donc écartée — la voix actuelle reste. Les détails sont dans app.log.', 'A voz baixada não passou na verificação, então eu a descartei — a atual continua. Os detalhes estão no app.log.')
_tr7('log.edge_update.error', '音声を更新できませんでした — いまの音声はそのままです。詳しくは app.log にあります。', '未能更新语音——当前的语音保持不变。详情见 app.log。', 'Голос не удалось обновить — текущий остаётся. Подробности в app.log.', 'No pude actualizar la voz: la actual se queda. Los detalles están en app.log.', 'Die Stimme ließ sich nicht aktualisieren — die bisherige bleibt. Details stehen in app.log.', 'Je n’ai pas pu mettre à jour la voix — la voix actuelle reste. Les détails sont dans app.log.', 'Não consegui atualizar a voz — a atual continua. Os detalhes estão no app.log.')
_tr7('log.edge_update.cancelled', '音声の更新を中断しました（見守りが始まったか、Windows の音声が選ばれています） — 何も変わっていません。', '我中断了语音更新（开始关注了，或选了 Windows 语音）——什么都没有改变。', 'Я прервала обновление голоса (началось наблюдение или выбран голос Windows) — ничего не изменилось.', 'Interrumpí la actualización de la voz (empezó la observación o se eligió la voz de Windows): no ha cambiado nada.', 'Ich habe das Aktualisieren der Stimme abgebrochen (die Beobachtung hat begonnen oder die Windows-Stimme ist gewählt) — nichts wurde geändert.', 'J’ai interrompu la mise à jour de la voix (l’observation a commencé ou la voix Windows est choisie) — rien n’a changé.', 'Interrompi a atualização da voz (a observação começou ou a voz do Windows foi escolhida) — nada mudou.')


# ==========================================================================
# CZECH AND BULGARIAN (0.2)
# ==========================================================================
#
# The translation of the whole app is in the module `i18n_cs_bg.py` (two
# dicts key -> text), so that this file does not grow by two more columns.
# It is inserted only here, after all `STRINGS.update` and `_tr7`, so it
# changes only cs and bg.
#
# A key without a Czech or Bulgarian translation (a new key, a full dict
# with nine languages) gets English - the same as `_sk_en` for the other
# languages - and tests/test_i18n_cs_bg.py reports it, so that it does not
# stay English silently. PyInstaller picks up the module through this
# import (and to be safe also through hiddenimports in Dandurf.spec).
from i18n_cs_bg import BG as _BG, CS as _CS  # noqa: E402

for _kod, _preklady in ((LANG_CS, _CS), (LANG_BG, _BG)):
    for _k, _v in _preklady.items():
        if _k in STRINGS:
            STRINGS[_k][_kod] = _v
for _zaznam in STRINGS.values():
    for _kod in (LANG_CS, LANG_BG):
        if _kod not in _zaznam:
            _zaznam[_kod] = _zaznam.get(LANG_EN, _zaznam.get(LANG_SK, ""))
