"""Preklady rozhrania - Slovencina / Anglictina / Japoncina / Cinstina
(zjednodusena) / Rustina / Spanielcina / Nemcina / Francuzstina /
Portugalcina (Brazilia) / Cestina / Bulharcina.

Sada jazykov = rozhranie appky (SK/EN/JA) + najpopularnejsie jazyky
hracov na Steame (Steam Hardware & Software Survey + Valve GDC'25 data)
+ cestina a bulharcina (0.2).

Cele UI sa po prepnuti jazyka prekresli odznova (rovnaky princip ako pri
prepnuti vizualnej temy), takze staci menit `_lang["code"]` a znova
zavolat `tr()` pri stavbe widgetov - ziadny widget si preklad
nepamataeta trvalo.

POZNAMKA K PREKLADOM: appka je pisana po slovensky; ostatne jazyky su
preklady s pomocou AI (Claude) a rodeny hovoriaci ich este nekontroloval
(appka to hovori aj sama - `settings.language_note` pod vyberom jazyka).
Odporucame pred sirokym vydanim appky necha' ich prejst rodenym
hovoriacim, najma obsah v guide.* (biomechanika/dychove techniky), kde
presnost formulacie ma realny vyznam.

Cestina a bulharcina maju preklad v samostatnom module `i18n_cs_bg.py` -
vklada sa na konci tohto suboru.
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
    """Text zaznamu v jazyku `code`; ked chyba, anglictina, potom slovencina.

    Kazdy kluc ma mat vsetky jazyky (strazi to tests/test_i18n_keys.py) -
    toto je poistka, aby neuplny zaznam (napr. plny slovnik s deviatimi
    jazykmi pri cestine a bulharcine) nikdy nezhodil okno ani neukazal
    slovencinu hracovi, ktory si vybral iny jazyk.
    """
    for kod in (code, LANG_EN, DEFAULT_LANG):
        if kod in entry:
            return entry[kod]
    return msg_key


def _format(entry, code, text, kwargs):
    """`text.format(**kwargs)` - pri chybnom preklade anglicky zdroj.

    Zle opisany {placeholder} v preklade nesmie zhodit okno. Placeholdery
    v zdroji strazi check_before_run.py; ked zlyha aj anglictina, je to
    chyba volania, nie prekladu - ta sa ukaze.
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


# Zvlastna hodnota pre "jazyk v hre" - drz sa jazyka rozhrania.
LANG_SAME_AS_APP = "app"


def _win_locale():
    """Kod locale prihlaseneho uzivatela, napr. 'de-DE'. Prazdny = neznamy.

    Oddelene od `system_lang()` kvoli testom - toto je jediny kus, ktory
    sa pyta operacneho systemu, takze sa da v teste vymenit a zvysok
    mapovania overit na vsetkych jazykoch (tests/test_i18n_cs_bg.py).
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
    """Jazyk Windowsu prelozeny na jeden z nasich jedenastich.

    PRECO TO EXISTUJE: pri prvom spusteni sa appka nastavovala na
    SLOVENCINU - lebo tak ju pisal autor. Stiahne si ju ale aj Nemec,
    Brazilcan alebo Japonec a prve, co uvidi, je jazyk, ktoremu nerozumie,
    a musi ho hladat v nastaveniach. Preto sa pri prvom starte berie jazyk
    systemu, a ked ho medzi nasimi jedenastimi nemame, anglictina - nie
    slovencina.

    Ulozena volba hraca ma vzdy prednost; toto sa pyta len vtedy, ked
    este ziadna nie je.
    """
    kod = _win_locale() or ""
    primarny = kod.replace("_", "-").lower().split("-")[0]
    # Cesky Windows dostaval do 0.2 slovencinu (cestina medzi jazykmi
    # nebola); od 0.2 ma cestina vlastny preklad, bulharcina tiez.
    if primarny in LANGUAGES:
        return primarny
    return default


def tr_lang(code, msg_key, **kwargs):
    """Preklad do KONKRETNEHO jazyka, nezavisle od jazyka rozhrania.

    Je to pre to, co appka kresli DO HRY (HUD vlavo dole, popisky pod
    vizualmi). Tie nevidi len hrac - vidia ich diváci na streame a
    kupujuci na screenshotoch v obchode. Rozhranie teda moze byt po
    slovensky a v hre moze byt anglictina.

    `code` mimo `LANGUAGES` (typicky `LANG_SAME_AS_APP`) znamena "pouzi
    jazyk rozhrania".
    """
    entry = STRINGS.get(msg_key)
    if entry is None:
        return msg_key
    code = code if code in LANGUAGES else _lang["code"]
    return _format(entry, code, _pick(entry, code, msg_key), kwargs)


STRINGS = {
    'app.tagline': {
        'sk': 'Mindfulness pripomienky pri hraní',
        'en': 'Mindfulness reminders while gaming',
        'ja': 'ゲーム中のマインドフルネス・リマインダー',
        'zh': '游戏中的正念提醒',
        'ru': 'Напоминания об осознанности во время игры',
        'es': 'Recordatorios de mindfulness mientras juegas',
        'de': 'Achtsamkeits-Erinnerungen beim Zocken',
        'fr': 'Rappels de pleine conscience pendant le jeu',
        'pt': 'Lembretes de mindfulness enquanto joga',
    },
    'nav.dashboard': {
        'sk': 'Prehľad',
        'en': 'Dashboard',
        'ja': 'ダッシュボード',
        'zh': '仪表盘',
        'ru': 'Панель',
        'es': 'Panel',
        'de': 'Übersicht',
        'fr': 'Tableau de bord',
        'pt': 'Painel',
    },
    'nav.profily': {
        'sk': 'Profily',
        'en': 'Profiles',
        'ja': 'プロファイル',
        'zh': '配置文件',
        'ru': 'Профили',
        'es': 'Perfiles',
        'de': 'Profile',
        'fr': 'Profils',
        'pt': 'Perfis',
    },
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
    'nav.guide': {
        'sk': '📖 Sprievodca',
        'en': '📖 Guide',
        'ja': '📖 ガイド',
        'zh': '📖 指南',
        'ru': '📖 Руководство',
        'es': '📖 Guía',
        'de': '📖 Anleitung',
        'fr': '📖 Guide',
        'pt': '📖 Guia',
    },
    'onboarding.welcome': {
        'sk': 'Vitaj v {app}',
        'en': 'Welcome to {app}',
        'ja': '{app} へようこそ',
        'zh': '欢迎使用 {app}',
        'ru': 'Добро пожаловать в {app}',
        'es': 'Bienvenido a {app}',
        'de': 'Willkommen bei {app}',
        'fr': 'Bienvenue dans {app}',
        'pt': 'Bem-vindo ao {app}',
    },
    'onboarding.hero.title': {
        'sk': 'Telo v pokoji. Myseľ v prítomnosti.',
        'en': 'Body at ease. Mind in the present.',
        'ja': '体は安らぎ、心は今ここに。',
        'zh': '身体放松，心在当下。',
        'ru': 'Тело расслаблено. Разум в настоящем.',
        'es': 'Cuerpo en calma. Mente en el presente.',
        'de': 'Körper entspannt. Geist im Moment.',
        'fr': 'Corps détendu. Esprit dans le présent.',
        'pt': 'Corpo tranquilo. Mente no presente.',
    },
    'onboarding.hero.symptom.cramp': {
        'sk': '⚡ Kŕč v ruke',
        'en': '⚡ Cramped hand',
        'ja': '⚡ 手のこわばり',
        'zh': '⚡ 手部抽筋',
        'ru': '⚡ Судорога в руке',
        'es': '⚡ Calambre en la mano',
        'de': '⚡ Verkrampfte Hand',
        'fr': '⚡ Main crispée',
        'pt': '⚡ Mão travada',
    },
    'onboarding.hero.symptom.jaw': {
        'sk': '🦷 Zaťatá čeľusť',
        'en': '🦷 Clenched jaw',
        'ja': '🦷 食いしばり',
        'zh': '🦷 咬紧牙关',
        'ru': '🦷 Стиснутая челюсть',
        'es': '🦷 Mandíbula apretada',
        'de': '🦷 Zusammengebissener Kiefer',
        'fr': '🦷 Mâchoire serrée',
        'pt': '🦷 Mandíbula travada',
    },
    'onboarding.hero.symptom.breath': {
        'sk': '🫁 Zadržaný dych',
        'en': '🫁 Held breath',
        'ja': '🫁 息を止める',
        'zh': '🫁 屏住呼吸',
        'ru': '🫁 Задержанное дыхание',
        'es': '🫁 Respiración contenida',
        'de': '🫁 Angehaltener Atem',
        'fr': '🫁 Respiration bloquée',
        'pt': '🫁 Respiração presa',
    },
    'onboarding.why.mission': {
        'sk': 'Táto appka netrénuje tvoj aim. Trénuje tvoju schopnosť odísť z hry pokojnejší, než si do nej vošiel.',
        'en': "This app doesn't train your aim. It trains your ability to leave the game calmer than you entered it.",
        'ja': 'このアプリはエイムを鍛えるものではありません。ゲームを始めたときより穏やかな状態で終える力を鍛えるものです。',
        'zh': '这个应用不会训练你的瞄准。它训练的是让你带着比进入游戏时更平静的状态离开游戏的能力。',
        'ru': 'Это приложение не тренирует твою меткость. Оно тренирует способность выходить из игры спокойнее, чем ты в неё вошёл.',
        'es': 'Esta app no entrena tu puntería. Entrena tu capacidad de salir del juego más tranquilo de lo que entraste.',
        'de': 'Diese App trainiert nicht dein Zielen. Sie trainiert deine Fähigkeit, das Spiel ruhiger zu verlassen, als du es betreten hast.',
        'fr': "Cette appli n'entraîne pas ta visée. Elle entraîne ta capacité à quitter la partie plus calme que tu n'y es entré.",
        'pt': 'Este app não treina sua mira. Ele treina sua capacidade de sair do jogo mais calmo do que entrou.',
    },
    'onboarding.why.continue': {
        'sk': 'Ukáž mi ako →',
        'en': 'Show me how →',
        'ja': '使い方を見る →',
        'zh': '看看怎么做 →',
        'ru': 'Покажи как →',
        'es': 'Muéstrame cómo →',
        'de': 'Zeig mir wie →',
        'fr': 'Montre-moi comment →',
        'pt': 'Me mostra como →',
    },
    'onboarding.question': {
        'sk': 'Ktoré prostredie ťa lepšie udrží v prítomnosti?',
        'en': 'Which environment keeps you more present?',
        'ja': 'どちらの空間が、あなたをより「今」に留めてくれますか？',
        'zh': '哪种环境让你更能保持专注当下？',
        'ru': 'Какая обстановка помогает тебе лучше оставаться в моменте?',
        'es': '¿Qué ambiente te ayuda a mantenerte más presente?',
        'de': 'Welche Umgebung hilft dir, präsenter zu bleiben?',
        'fr': "Quel environnement t'aide à rester plus présent ?",
        'pt': 'Qual ambiente te ajuda a ficar mais presente?',
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
    'onboarding.diag.title': {
        'sk': 'Diagnostika herného tieňa',
        'en': 'Diagnose your gaming shadow',
        'ja': 'ゲーム中の「影」を診断',
        'zh': '诊断你的游戏阴影',
        'ru': 'Диагностика твоей игровой тени',
        'es': 'Diagnostica tu sombra de juego',
        'de': 'Diagnostiziere deinen Gaming-Schatten',
        'fr': 'Diagnostique ton ombre de jeu',
        'pt': 'Diagnostique sua sombra no jogo',
    },
    'onboarding.diag.subtitle': {
        'sk': 'Zaškrtni, čo sa ti pri hraní stáva — appka podľa toho predvolene zapne alebo vypne zodpovedajúce sloty. Vždy si to vieš neskôr prenastaviť.',
        'en': 'Check what happens to you while gaming - the app will enable or disable the matching slots by default. You can always change this later.',
        'ja': 'ゲーム中に起きることをチェックしてください - それに応じて対応するスロットが初期設定で有効/無効になります。後からいつでも変更できます。',
        'zh': '勾选你在游戏中会出现的状况——应用会据此默认启用或停用对应的插槽。你随时都可以之后再调整。',
        'ru': 'Отметь, что с тобой происходит во время игры — приложение по умолчанию включит или отключит соответствующие слоты. Это всегда можно изменить позже.',
        'es': 'Marca lo que te pasa mientras juegas - la app activará o desactivará por defecto los slots correspondientes. Siempre puedes cambiarlo después.',
        'de': 'Kreuze an, was dir beim Zocken passiert - die App aktiviert oder deaktiviert standardmäßig die passenden Slots. Du kannst das jederzeit später ändern.',
        'fr': "Coche ce qui t'arrive en jouant - l'appli activera ou désactivera par défaut les slots correspondants. Tu peux toujours changer ça plus tard.",
        'pt': 'Marque o que acontece com você enquanto joga - o app vai ativar ou desativar por padrão os slots correspondentes. Você sempre pode mudar isso depois.',
    },
    'onboarding.diag.item1': {
        'sk': '1. Trasenie rúk / kŕčovitý stisk myši pri mierení',
        'en': '1. Shaky hands / a death-grip on the mouse while aiming',
        'ja': '1. 手の震え／エイム中にマウスを握りしめる',
        'zh': '1. 瞄准时手在发抖／死死握住鼠标',
        'ru': '1. Дрожащие руки / мёртвая хватка на мышке при прицеливании',
        'es': '1. Manos temblorosas / agarre mortal del ratón al apuntar',
        'de': '1. Zittrige Hände / Todesgriff an der Maus beim Zielen',
        'fr': '1. Mains tremblantes / prise mortelle sur la souris en visant',
        'pt': '1. Mãos trêmulas / aperto mortal no mouse ao mirar',
    },
    'onboarding.diag.item1_hint': {
        'sk': '→ Aktivuje Slot 3 (ADS / pravé tlačidlo: „Release“ + tibetská miska)',
        'en': '→ Enables Slot 3 (ADS / right button: "Release" + singing bowl)',
        'ja': '→ スロット3を有効化（ADS／右クリック：「解放」+ シンギングボウル）',
        'zh': '→ 启用插槽3（开镜／右键："松开" + 颂钵声）',
        'ru': '→ Включает слот 3 (прицеливание / ПКМ: «Отпусти» + поющая чаша)',
        'es': '→ Activa el Slot 3 (apuntar / botón derecho: «Suelta» + cuenco cantor)',
        'de': '→ Aktiviert Slot 3 (Zielen / rechte Maustaste: „Loslassen“ + Klangschale)',
        'fr': '→ Active le Slot 3 (visée / clic droit : « Relâche » + bol chantant)',
        'pt': '→ Ativa o Slot 3 (mira / botão direito: "Solta" + tigela tibetana)',
    },
    'onboarding.diag.item2': {
        'sk': '2. Zaťaté zuby a bolesť čeľuste/krku po hraní',
        'en': '2. A clenched jaw and jaw/neck pain after playing',
        'ja': '2. 食いしばりと、プレイ後の顎・首の痛み',
        'zh': '2. 游戏后下颌紧咬、颈部或下颌疼痛',
        'ru': '2. Стиснутая челюсть, боль в челюсти/шее после игры',
        'es': '2. Mandíbula apretada y dolor de mandíbula/cuello tras jugar',
        'de': '2. Zusammengebissener Kiefer und Kiefer-/Nackenschmerzen nach dem Spielen',
        'fr': '2. Mâchoire serrée et douleurs à la mâchoire/au cou après avoir joué',
        'pt': '2. Mandíbula travada e dor na mandíbula/pescoço após jogar',
    },
    'onboarding.diag.item2_hint': {
        'sk': '→ Aktivuje Slot 2 (Prebíjanie / R: „Jaw“ + drevený blok)',
        'en': '→ Enables Slot 2 (Reload / R: "Jaw" + wood temple block)',
        'ja': '→ スロット2を有効化（リロード／R：「顎」+ 木製テンプルブロック）',
        'zh': '→ 启用插槽2（换弹／R键："牙关" + 木鱼声）',
        'ru': '→ Включает слот 2 (перезарядка / R: «Челюсть» + деревянный храмовый блок)',
        'es': '→ Activa el Slot 2 (recargar / R: «Mandíbula» + bloque de madera de templo)',
        'de': '→ Aktiviert Slot 2 (Nachladen / R: „Kiefer“ + Holz-Tempelblock)',
        'fr': '→ Active le Slot 2 (recharger / R : « Mâchoire » + bloc de bois de temple)',
        'pt': '→ Ativa o Slot 2 (recarregar / R: "Mandíbula" + bloco de madeira de templo)',
    },
    'onboarding.diag.item3': {
        'sk': '3. Predkláňanie sa k monitoru a strata stability',
        'en': '3. Leaning into the monitor and losing your grounding',
        'ja': '3. モニターに前のめりになり、安定を失う',
        'zh': '3. 身体前倾贴近显示器，失去稳定感',
        'ru': '3. Наклон к монитору и потеря устойчивости',
        'es': '3. Inclinarte hacia el monitor y perder el equilibrio',
        'de': '3. Nach vorne zum Monitor lehnen und die Bodenhaftung verlieren',
        'fr': "3. Se pencher vers l'écran et perdre son ancrage",
        'pt': '3. Inclinar-se para o monitor e perder o aterramento',
    },
    'onboarding.diag.item3_hint': {
        'sk': '→ Aktivuje Slot 1 (Crouch / C: „Grounded“ + zemitý dopad)',
        'en': '→ Enables Slot 1 (Crouch / C: "Grounded" + earth thud)',
        'ja': '→ スロット1を有効化（しゃがみ／C：「重心」+ 地鳴りの音）',
        'zh': '→ 启用插槽1（下蹲／C键："落地" + 大地撞击声）',
        'ru': '→ Включает слот 1 (присед / C: «Опора» + удар о землю)',
        'es': '→ Activa el Slot 1 (agacharse / C: «Con los pies en la tierra» + golpe de tierra)',
        'de': '→ Aktiviert Slot 1 (Ducken / C: „Geerdet“ + Erd-Aufprall)',
        'fr': "→ Active le Slot 1 (s'accroupir / C : « Ancré » + impact au sol)",
        'pt': '→ Ativa o Slot 1 (agachar / C: "Aterrado" + impacto de terra)',
    },
    'onboarding.diag.item4': {
        'sk': '4. Zadržiavanie dychu v prestrelkách a panika',
        'en': '4. Holding your breath in firefights, then panic',
        'ja': '4. 撃ち合い中に息を止め、パニックになる',
        'zh': '4. 交火时屏住呼吸，随后陷入恐慌',
        'ru': '4. Задержка дыхания в перестрелках, затем паника',
        'es': '4. Contener la respiración en tiroteos, luego pánico',
        'de': '4. Atem anhalten in Feuergefechten, dann Panik',
        'fr': '4. Retenir sa respiration dans les échanges de tirs, puis paniquer',
        'pt': '4. Prender a respiração em trocas de tiro, depois entrar em pânico',
    },
    'onboarding.diag.item4_hint': {
        'sk': '→ Aktivuje Slot 4 (Dych / F: „Breathe“ + výdych)',
        'en': '→ Enables Slot 4 (Breath / F: "Breathe" + soft exhale)',
        'ja': '→ スロット4を有効化（呼吸／F：「呼吸」+ 息の音）',
        'zh': '→ 启用插槽4（呼吸／F键："呼吸" + 轻柔呼气声）',
        'ru': '→ Включает слот 4 (дыхание / F: «Дыши» + мягкий выдох)',
        'es': '→ Activa el Slot 4 (respiración / F: «Respira» + exhalación suave)',
        'de': '→ Aktiviert Slot 4 (Atem / F: „Atme“ + sanftes Ausatmen)',
        'fr': '→ Active le Slot 4 (respiration / F : « Respire » + expiration douce)',
        'pt': '→ Ativa o Slot 4 (respiração / F: "Respira" + expiração suave)',
    },
    'onboarding.diag.continue': {
        'sk': 'Ďalej →',
        'en': 'Next →',
        'ja': '次へ →',
        'zh': '下一步 →',
        'ru': 'Далее →',
        'es': 'Siguiente →',
        'de': 'Weiter →',
        'fr': 'Suivant →',
        'pt': 'Próximo →',
    },
    'onboarding.test_sound': {
        'sk': '🔊 Vyskúšať zvuk a hlasitosť',
        'en': '🔊 Test sound and volume',
        'ja': '🔊 音とボリュームを試す',
        'zh': '🔊 测试声音与音量',
        'ru': '🔊 Проверить звук и громкость',
        'es': '🔊 Probar sonido y volumen',
        'de': '🔊 Ton und Lautstärke testen',
        'fr': '🔊 Tester le son et le volume',
        'pt': '🔊 Testar som e volume',
    },
    'assets.preparing': {
        'sk': 'Pripravujem audio balíčky (Zen & Modern)...',
        'en': 'Preparing audio packages (Zen & Modern)...',
        'ja': 'オーディオパッケージを準備中（Zen & Modern）...',
        'zh': '正在准备音频素材包（禅意版和现代版）…',
        'ru': 'Подготовка звуковых пакетов (Дзен и Модерн)…',
        'es': 'Preparando paquetes de audio (Zen y Moderno)...',
        'de': 'Audio-Pakete werden vorbereitet (Zen & Modern) ...',
        'fr': 'Préparation des packs audio (Zen et Moderne)...',
        'pt': 'Preparando pacotes de áudio (Zen e Moderno)...',
    },
    'assets.ready': {
        'sk': 'Audio balíčky pripravené ✓',
        'en': 'Audio packages ready ✓',
        'ja': 'オーディオパッケージ準備完了 ✓',
        'zh': '音频素材包已就绪 ✓',
        'ru': 'Звуковые пакеты готовы ✓',
        'es': 'Paquetes de audio listos ✓',
        'de': 'Audio-Pakete bereit ✓',
        'fr': 'Packs audio prêts ✓',
        'pt': 'Pacotes de áudio prontos ✓',
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
    'profile.label': {
        'sk': 'Profil hry:',
        'en': 'Game profile:',
        'ja': 'ゲームプロファイル:',
        'zh': '游戏配置文件：',
        'ru': 'Игровой профиль:',
        'es': 'Perfil de juego:',
        'de': 'Spielprofil:',
        'fr': 'Profil de jeu :',
        'pt': 'Perfil do jogo:',
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
        'sk': "Naozaj odstrániť profil '{name}' aj so všetkými jeho slotmi?",
        'en': "Really delete profile '{name}' and all of its slots?",
        'ja': 'プロファイル「{name}」とそのすべてのスロットを削除しますか？',
        'zh': '确定要删除配置文件「{name}」及其所有插槽吗？',
        'ru': 'Действительно удалить профиль «{name}» и все его слоты?',
        'es': '¿Eliminar de verdad el perfil «{name}» y todos sus slots?',
        'de': 'Profil „{name}“ und alle seine Slots wirklich löschen?',
        'fr': 'Vraiment supprimer le profil « {name} » et tous ses slots ?',
        'pt': 'Excluir mesmo o perfil "{name}" e todos os seus slots?',
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
        'sk': 'Automaticky prepnúť profil podľa bežiacej hry',
        'en': 'Auto-switch profile based on the running game',
        'ja': '起動中のゲームに応じてプロファイルを自動切替',
        'zh': '根据正在运行的游戏自动切换配置文件',
        'ru': 'Автоматически переключать профиль по запущенной игре',
        'es': 'Cambiar perfil automáticamente según el juego en ejecución',
        'de': 'Profil automatisch je nach laufendem Spiel wechseln',
        'fr': 'Changer automatiquement de profil selon le jeu en cours',
        'pt': 'Trocar de perfil automaticamente conforme o jogo em execução',
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
    'settings.overlay_button': {
        'sk': '🎮 In-Game Vizuály (Overlay)…',
        'en': '🎮 In-Game Visuals (Overlay)…',
        'ja': '🎮 ゲーム内ビジュアル（オーバーレイ）…',
        'zh': '🎮 游戏内视觉效果（叠加层）…',
        'ru': '🎮 Визуалы в игре (оверлей)…',
        'es': '🎮 Visuales en el juego (Overlay)…',
        'de': '🎮 In-Game-Visuals (Overlay) …',
        'fr': '🎮 Visuels en jeu (Overlay)…',
        'pt': '🎮 Visuais no jogo (Overlay)…',
    },
    'overlay.dialog_title': {
        'sk': 'In-Game Vizuály (Overlay)',
        'en': 'In-Game Visuals (Overlay)',
        'ja': 'ゲーム内ビジュアル（オーバーレイ）',
        'zh': '游戏内视觉效果（叠加层）',
        'ru': 'Визуалы в игре (оверлей)',
        'es': 'Visuales en el juego (Overlay)',
        'de': 'In-Game-Visuals (Overlay)',
        'fr': 'Visuels en jeu (Overlay)',
        'pt': 'Visuais no jogo (Overlay)',
    },
    'overlay.dialog_hint': {
        'sk': 'Pre každý slot nastav, či sa má v hre zobraziť vlastný vizuál, jeho veľkosť a polohu na obrazovke. Tlačidlo Test ho zobrazí a nechá na obrazovke — chyť ho myšou a potiahni, kam chceš; druhým klikom polohu uložíš.',
        'en': "For each slot, choose whether it shows its own in-game visual, plus its size and screen position. The Test button shows it and keeps it on screen — grab it with the mouse and drag it wherever you want; click again to save the position.",
        'ja': '各スロットについて、ゲーム内に専用のビジュアルを表示するかどうか、そのサイズと画面上の位置を設定できます。「テスト」ボタンで表示したまま、マウスでつかんで好きな場所へドラッグできます。もう一度押すと位置が保存されます。',
        'zh': '为每个插槽选择是否显示对应的游戏内视觉效果，以及它的大小和屏幕位置。点击测试按钮后它会一直显示在屏幕上——用鼠标拖到任意位置，再点一次即可保存位置。',
        'ru': 'Для каждого слота выбери, показывать ли собственный визуал в игре, а также его размер и положение на экране. Кнопка «Тест» покажет его и оставит на экране — схвати его мышью и перетащи куда хочешь; повторное нажатие сохранит положение.',
        'es': 'Para cada slot, elige si muestra su propio visual en el juego, además de su tamaño y posición en pantalla. El botón Probar lo muestra y lo deja en pantalla: agárralo con el ratón y arrástralo donde quieras; vuelve a pulsar para guardar la posición.',
        'de': 'Wähle für jeden Slot, ob er sein eigenes In-Game-Visual zeigt, sowie dessen Größe und Bildschirmposition. Der Test-Button blendet es ein und lässt es auf dem Bildschirm – greif es mit der Maus und zieh es, wohin du willst; ein zweiter Klick speichert die Position.',
        'fr': "Pour chaque slot, choisis s'il affiche son propre visuel en jeu, ainsi que sa taille et sa position à l'écran. Le bouton Tester l'affiche et le laisse à l'écran : attrape-le à la souris et glisse-le où tu veux ; un second clic enregistre la position.",
        'pt': 'Para cada slot, escolha se ele mostra seu próprio visual no jogo, além do tamanho e da posição na tela. O botão Testar o exibe e o mantém na tela: pegue-o com o mouse e arraste para onde quiser; clique de novo para salvar a posição.',
    },
    'overlay.slot.0': {
        'sk': '🥾 Ťažisko (drep/slide)',
        'en': '🥾 Grounding (crouch/slide)',
        'ja': '🥾 グラウンディング（しゃがみ/スライド）',
        'zh': '🥾 稳定重心（下蹲／滑行）',
        'ru': '🥾 Опора (присед/слайд)',
        'es': '🥾 Con los pies en la tierra (agacharse/deslizarse)',
        'de': '🥾 Erdung (Ducken/Slide)',
        'fr': "🥾 Ancrage (s'accroupir/glisser)",
        'pt': '🥾 Aterramento (agachar/deslizar)',
    },
    'overlay.slot.1': {
        'sk': '💀 Čeľusť (prebíjanie)',
        'en': '💀 Jaw (reload)',
        'ja': '💀 顎（リロード）',
        'zh': '💀 下颌（换弹）',
        'ru': '💀 Челюсть (перезарядка)',
        'es': '💀 Mandíbula (recargar)',
        'de': '💀 Kiefer (Nachladen)',
        'fr': '💀 Mâchoire (recharger)',
        'pt': '💀 Mandíbula (recarregar)',
    },
    'overlay.slot.2': {
        'sk': '🖱️ Uvoľnenie (myš)',
        'en': '🖱️ Release (mouse)',
        'ja': '🖱️ リリース（マウス）',
        'zh': '🖱️ 放松（鼠标）',
        'ru': '🖱️ Отпусти (мышь)',
        'es': '🖱️ Suelta (ratón)',
        'de': '🖱️ Loslassen (Maus)',
        'fr': '🖱️ Relâche (souris)',
        'pt': '🖱️ Solta (mouse)',
    },
    # Cyklus uz nie je pevny (viz overlay.breath_seconds nizsie), preto bez
    # "20 s" - presnu dlzku vidiet priamo v posuvnikoch pod tymto nadpisom.
    'overlay.slot.3': {
        'sk': '🫁 Dych',
        'en': '🫁 Breath',
        'ja': '🫁 呼吸',
        'zh': '🫁 呼吸',
        'ru': '🫁 Дыхание',
        'es': '🫁 Respiración',
        'de': '🫁 Atem',
        'fr': '🫁 Respiration',
        'pt': '🫁 Respiração',
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
        # bez "(3 s)" - test uz nie je 3-sekundova ukazka, ale drag & drop
        # rezim, ktory bezi, kym ho hrac nevypne (viz overlay._SlotOverlay.test)
        'sk': '▶ Test vizuálu',
        'en': '▶ Test visual',
        'ja': '▶ ビジュアルをテスト',
        'zh': '▶ 测试视觉效果',
        'ru': '▶ Тест визуала',
        'es': '▶ Probar visual',
        'de': '▶ Visual testen',
        'fr': '▶ Tester le visuel',
        'pt': '▶ Testar visual',
    },
    'overlay.visual.jaw_label': {
        'sk': 'UVOĽNI ČEĽUSŤ',
        'en': 'RELAX JAW',
        'ja': '顎の力を抜く',
        'zh': '放松下颌',
        'ru': 'РАССЛАБЬ ЧЕЛЮСТЬ',
        'es': 'RELAJA LA MANDÍBULA',
        'de': 'KIEFER ENTSPANNEN',
        'fr': 'RELÂCHE LA MÂCHOIRE',
        'pt': 'RELAXE A MANDÍBULA',
    },
    'log.auto_profile_created': {
        'sk': "Rozpoznaná hra '{name}' — vytvorený nový profil s predvolenými slotmi.",
        'en': "Detected game '{name}' - created a new profile with default slots.",
        'ja': 'ゲーム「{name}」を検出 - デフォルトスロットで新規プロファイルを作成しました。',
        'zh': '检测到游戏「{name}」- 已创建带默认插槽的新配置文件。',
        'ru': 'Обнаружена игра «{name}» - создан новый профиль со стандартными слотами.',
        'es': 'Juego «{name}» detectado - se creó un nuevo perfil con slots predeterminados.',
        'de': 'Spiel „{name}“ erkannt - neues Profil mit Standard-Slots erstellt.',
        'fr': 'Jeu « {name} » détecté - nouveau profil créé avec les slots par défaut.',
        'pt': 'Jogo "{name}" detectado - novo perfil criado com slots padrão.',
    },
    'log.auto_profile_detected': {
        'sk': "Rozpoznaná hra '{name}' — profil prepnutý, odpočúvanie zapnuté.",
        'en': "Detected game '{name}' - profile switched, listening turned on.",
        'ja': 'ゲーム「{name}」を検出 - プロファイルを切替え、リスニングを開始しました。',
        'zh': '检测到游戏「{name}」- 已切换配置文件并开启监听。',
        'ru': 'Обнаружена игра «{name}» - профиль переключён, прослушивание включено.',
        'es': 'Juego «{name}» detectado - perfil cambiado, escucha activada.',
        'de': 'Spiel „{name}“ erkannt - Profil gewechselt, Zuhören aktiviert.',
        'fr': 'Jeu « {name} » détecté - profil changé, écoute activée.',
        'pt': 'Jogo "{name}" detectado - perfil trocado, escuta ativada.',
    },
    'log.auto_profile_ended': {
        'sk': 'Hra už nebeží — odpočúvanie pozastavené (režim spánku).',
        'en': 'Game is no longer running - listening paused (sleep mode).',
        'ja': 'ゲームが終了しました - リスニングを一時停止しました（スリープモード）。',
        'zh': '游戏已不再运行 - 监听已暂停（休眠模式）。',
        'ru': 'Игра больше не запущена - прослушивание приостановлено (режим сна).',
        'es': 'El juego ya no está en ejecución - escucha en pausa (modo reposo).',
        'de': 'Spiel läuft nicht mehr - Zuhören pausiert (Ruhemodus).',
        'fr': "Le jeu n'est plus en cours - écoute mise en pause (mode veille).",
        'pt': 'O jogo não está mais em execução - escuta pausada (modo de espera).',
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
    'settings.strict_global_lock': {
        'sk': 'Striktný globálny zámok (jeden spustený slot zablokuje všetky ostatné)',
        'en': 'Strict global lock (one fired slot blocks all others)',
        'ja': '厳格なグローバルロック（1つのスロットが発火すると他をすべてブロック）',
        'zh': '严格全局锁定（一个插槽触发时会阻止其他所有插槽）',
        'ru': 'Строгая глобальная блокировка (сработавший слот блокирует все остальные)',
        'es': 'Bloqueo global estricto (un slot activado bloquea todos los demás)',
        'de': 'Strikte globale Sperre (ein ausgelöster Slot blockiert alle anderen)',
        'fr': 'Verrouillage global strict (un slot déclenché bloque tous les autres)',
        'pt': 'Bloqueio global estrito (um slot acionado bloqueia todos os outros)',
    },
    'log.strict_lock_on': {
        'sk': 'Striktný globálny zámok zapnutý — spustenie ktoréhokoľvek slotu teraz zablokuje všetky ostatné na dĺžku globálneho cooldownu.',
        'en': 'Strict global lock turned on - firing any slot now blocks all others for the length of the global cooldown.',
        'ja': '厳格なグローバルロックをオンにしました - いずれかのスロットが発火すると、グローバルクールダウンの間、他のすべてのスロットがブロックされます。',
        'zh': '严格全局锁定已开启 - 现在只要触发任意插槽，就会在全局冷却时间内阻止其他所有插槽。',
        'ru': 'Строгая глобальная блокировка включена - срабатывание любого слота теперь блокирует все остальные на время глобального кулдауна.',
        'es': 'Bloqueo global estricto activado - activar cualquier slot ahora bloquea todos los demás durante la duración del cooldown global.',
        'de': 'Strikte globale Sperre aktiviert - das Auslösen eines beliebigen Slots blockiert jetzt alle anderen für die Dauer des globalen Cooldowns.',
        'fr': "Verrouillage global strict activé - déclencher n'importe quel slot bloque désormais tous les autres pendant la durée du cooldown global.",
        'pt': 'Bloqueio global estrito ativado - acionar qualquer slot agora bloqueia todos os outros durante o cooldown global.',
    },
    'log.strict_lock_off': {
        'sk': 'Striktný globálny zámok vypnutý — každý slot sa opäť riadi len svojím vlastným cooldownom.',
        'en': 'Strict global lock turned off - each slot goes back to following only its own cooldown.',
        'ja': '厳格なグローバルロックをオフにしました - 各スロットは再び自身のクールダウンのみに従います。',
        'zh': '严格全局锁定已关闭 - 每个插槽重新只遵循自己的冷却时间。',
        'ru': 'Строгая глобальная блокировка отключена - каждый слот снова следует только своему собственному кулдауну.',
        'es': 'Bloqueo global estricto desactivado - cada slot vuelve a seguir solo su propio cooldown.',
        'de': 'Strikte globale Sperre deaktiviert - jeder Slot folgt wieder nur seinem eigenen Cooldown.',
        'fr': 'Verrouillage global strict désactivé - chaque slot suit à nouveau uniquement son propre cooldown.',
        'pt': 'Bloqueio global estrito desativado - cada slot volta a seguir apenas seu próprio cooldown.',
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
    'settings.hr_ip_label': {
        'sk': 'IP adresa',
        'en': 'IP address',
        'ja': 'IPアドレス',
        'zh': 'IP 地址',
        'ru': 'IP-адрес',
        'es': 'Dirección IP',
        'de': 'IP-Adresse',
        'fr': 'Adresse IP',
        'pt': 'Endereço IP',
    },
    'settings.hr_ip_hint': {
        'sk': 'Nechaj 0.0.0.0 — appka počúva na všetkých sieťach. Toto je adresa tvojho počítača, nie hodiniek. Nevieš, čo sem dať? Klikni na „Ako spárovať hodinky“ nižšie.',
        'en': "Leave 0.0.0.0 — the app listens on every network. This is your PC's address, not the watch's. Not sure what goes here? Click “How to pair your watch“ below.",
        'ja': "Leave 0.0.0.0 — the app listens on every network. This is your PC's address, not the watch's. Not sure what goes here? Click “How to pair your watch“ below.",
        'zh': "Leave 0.0.0.0 — the app listens on every network. This is your PC's address, not the watch's. Not sure what goes here? Click “How to pair your watch“ below.",
        'ru': "Leave 0.0.0.0 — the app listens on every network. This is your PC's address, not the watch's. Not sure what goes here? Click “How to pair your watch“ below.",
        'es': "Leave 0.0.0.0 — the app listens on every network. This is your PC's address, not the watch's. Not sure what goes here? Click “How to pair your watch“ below.",
        'de': "Leave 0.0.0.0 — the app listens on every network. This is your PC's address, not the watch's. Not sure what goes here? Click “How to pair your watch“ below.",
        'fr': "Leave 0.0.0.0 — the app listens on every network. This is your PC's address, not the watch's. Not sure what goes here? Click “How to pair your watch“ below.",
        'pt': "Leave 0.0.0.0 — the app listens on every network. This is your PC's address, not the watch's. Not sure what goes here? Click “How to pair your watch“ below.",
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
        'sk': 'Nechaj 4455, ak nevieš. Musí to byť rovnaké číslo ako v appke na hodinkách. Podrobný postup je v „Ako spárovať hodinky“.',
        'en': 'Leave 4455 if unsure. It must be the same number as in the watch app. Full steps are in “How to pair your watch“.',
        'ja': 'Leave 4455 if unsure. It must be the same number as in the watch app. Full steps are in “How to pair your watch“.',
        'zh': 'Leave 4455 if unsure. It must be the same number as in the watch app. Full steps are in “How to pair your watch“.',
        'ru': 'Leave 4455 if unsure. It must be the same number as in the watch app. Full steps are in “How to pair your watch“.',
        'es': 'Leave 4455 if unsure. It must be the same number as in the watch app. Full steps are in “How to pair your watch“.',
        'de': 'Leave 4455 if unsure. It must be the same number as in the watch app. Full steps are in “How to pair your watch“.',
        'fr': 'Leave 4455 if unsure. It must be the same number as in the watch app. Full steps are in “How to pair your watch“.',
        'pt': 'Leave 4455 if unsure. It must be the same number as in the watch app. Full steps are in “How to pair your watch“.',
    },
    'settings.hr_enable_switch': {
        'sk': 'Zapnúť senzor tepu',
        'en': 'Turn on the heart-rate sensor',
        'ja': 'Turn on the heart-rate sensor',
        'zh': 'Turn on the heart-rate sensor',
        'ru': 'Turn on the heart-rate sensor',
        'es': 'Turn on the heart-rate sensor',
        'de': 'Turn on the heart-rate sensor',
        'fr': 'Turn on the heart-rate sensor',
        'pt': 'Turn on the heart-rate sensor',
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
    'settings.hr_status_waiting': {
        'sk': 'Hodinky pripojené — čakám na tep…',
        'en': 'Watch connected — waiting for heart rate…',
        'ja': '時計が接続されました — 心拍を待っています…',
        'zh': '手表已连接 — 正在等待心率…',
        'ru': 'Часы подключены — жду пульс…',
        'es': 'Reloj conectado — esperando el ritmo cardíaco…',
        'de': 'Uhr verbunden — warte auf Herzfrequenz…',
        'fr': 'Montre connectée — en attente du rythme cardiaque…',
        'pt': 'Relógio conectado — aguardando a frequência cardíaca…',
    },
    'log.hr_client_connected': {
        'sk': 'Hodinky sa pripojili. Ak tep aj tak nechodí, vyber si v appke na hodinkách scénu „Zanshin“ a textový zdroj „Tep“ — a over, či hodinky naozaj merajú.',
        'en': 'The watch connected. If no heart rate arrives anyway, pick the "Zanshin" scene and the "Tep" text source in the watch app — and check that the watch is actually measuring.',
        'ja': '時計が接続しました。それでも心拍が届かない場合は、時計アプリで「Zanshin」シーンと「Tep」テキストソースを選び、時計が実際に計測しているか確認してください。',
        'zh': '手表已连接。如果仍然收不到心率，请在手表应用中选择"Zanshin"场景和"Tep"文本源，并确认手表确实在测量。',
        'ru': 'Часы подключились. Если пульс всё равно не приходит, выбери в приложении на часах сцену «Zanshin» и текстовый источник «Tep» — и проверь, что часы действительно измеряют.',
        'es': 'El reloj se conectó. Si aun así no llega el ritmo cardíaco, elige la escena "Zanshin" y la fuente de texto "Tep" en la app del reloj, y comprueba que el reloj esté midiendo.',
        'de': 'Die Uhr hat sich verbunden. Kommt trotzdem keine Herzfrequenz an, wähle in der Uhren-App die Szene "Zanshin" und die Textquelle "Tep" - und prüfe, ob die Uhr wirklich misst.',
        'fr': "La montre s'est connectée. Si le rythme cardiaque n'arrive toujours pas, choisis la scène « Zanshin » et la source texte « Tep » dans l'appli de la montre, et vérifie que la montre mesure vraiment.",
        'pt': 'O relógio conectou. Se mesmo assim a frequência cardíaca não chegar, escolha a cena "Zanshin" e a fonte de texto "Tep" no app do relógio - e confirme que o relógio está medindo.',
    },
    'log.hr_client_gone': {
        'sk': 'Hodinky sa odpojili.',
        'en': 'The watch disconnected.',
        'ja': '時計の接続が切れました。',
        'zh': '手表已断开连接。',
        'ru': 'Часы отключились.',
        'es': 'El reloj se desconectó.',
        'de': 'Die Uhr hat die Verbindung getrennt.',
        'fr': "La montre s'est déconnectée.",
        'pt': 'O relógio se desconectou.',
    },
    'log.hr_enabled': {
        'sk': 'Monitorovanie tepu zapnuté — čaká sa na dáta z {ip}:{port}.',
        'en': 'Heart rate monitoring enabled - waiting for data on {ip}:{port}.',
        'ja': '心拍モニタリングを有効にしました - {ip}:{port} からのデータを待機中。',
        'zh': '心率监测已启用 - 正在等待来自 {ip}:{port} 的数据。',
        'ru': 'Мониторинг пульса включён - ожидание данных с {ip}:{port}.',
        'es': 'Monitorización del ritmo cardíaco activada - esperando datos de {ip}:{port}.',
        'de': 'Herzfrequenzüberwachung aktiviert - warte auf Daten von {ip}:{port}.',
        'fr': 'Surveillance du rythme cardiaque activée - en attente de données depuis {ip}:{port}.',
        'pt': 'Monitoramento de frequência cardíaca ativado - aguardando dados de {ip}:{port}.',
    },
    'log.hr_disabled': {
        'sk': 'Monitorovanie tepu vypnuté.',
        'en': 'Heart rate monitoring disabled.',
        'ja': '心拍モニタリングを無効にしました。',
        'zh': '心率监测已停用。',
        'ru': 'Мониторинг пульса отключён.',
        'es': 'Monitorización del ritmo cardíaco desactivada.',
        'de': 'Herzfrequenzüberwachung deaktiviert.',
        'fr': 'Surveillance du rythme cardiaque désactivée.',
        'pt': 'Monitoramento de frequência cardíaca desativado.',
    },
    'log.hr_port_busy': {
        'sk': 'Port {port} už používa iný program — najčastejšie druhá otvorená kópia Zanshinu alebo bežiace OBS. Zavri ju a monitorovanie tepu zapni znova.',
        'en': 'Port {port} is already used by another program - usually a second open copy of Zanshin, or OBS running. Close it and turn heart rate monitoring back on.',
        'ja': 'ポート {port} は既に別のプログラムが使用しています - 多くの場合、Zanshin の2つ目のコピーか、起動中の OBS です。閉じてから心拍モニタリングを再度オンにしてください。',
        'zh': '端口 {port} 已被其他程序占用 - 通常是第二个打开的 Zanshin 副本或正在运行的 OBS。关闭它后再重新开启心率监测。',
        'ru': 'Порт {port} уже занят другой программой — чаще всего это вторая открытая копия Zanshin или запущенный OBS. Закрой её и снова включи мониторинг пульса.',
        'es': 'El puerto {port} ya lo usa otro programa: normalmente una segunda copia abierta de Zanshin, u OBS en ejecución. Ciérralo y vuelve a activar la monitorización.',
        'de': 'Port {port} wird bereits von einem anderen Programm benutzt - meist eine zweite offene Kopie von Zanshin oder ein laufendes OBS. Schließe es und schalte die Herzfrequenzüberwachung wieder ein.',
        'fr': "Le port {port} est déjà utilisé par un autre programme - le plus souvent une seconde copie de Zanshin ouverte, ou OBS en cours d'exécution. Ferme-la puis réactive la surveillance du rythme cardiaque.",
        'pt': 'A porta {port} já está em uso por outro programa - normalmente uma segunda cópia aberta do Zanshin, ou o OBS em execução. Feche-o e ative o monitoramento novamente.',
    },
    'log.hr_socket_error': {
        'sk': 'Monitorovanie tepu sa nepodarilo spustiť (IP/port): {err}',
        'en': 'Failed to start heart rate monitoring (IP/port): {err}',
        'ja': '心拍モニタリングを開始できませんでした（IP/ポート）: {err}',
        'zh': '心率监测启动失败（IP/端口）：{err}',
        'ru': 'Не удалось запустить мониторинг пульса (IP/порт): {err}',
        'es': 'No se pudo iniciar la monitorización del ritmo cardíaco (IP/puerto): {err}',
        'de': 'Herzfrequenzüberwachung konnte nicht gestartet werden (IP/Port): {err}',
        'fr': "Impossible de démarrer la surveillance du rythme cardiaque (IP/port) : {err}",
        'pt': 'Falha ao iniciar o monitoramento de frequência cardíaca (IP/porta): {err}',
    },
    # Uz sa nikam nelogguje - spustac z fazy 1 (tep nad kritickou 5 s ->
    # dychovy kruh) je zmazany (app.py, B28). Cita ho len ilustracia HUD v
    # onboardingu (ui_dialogs.py, krok 3, rez [:40]) - preto kratky pravdivy
    # text, ktory sa do 40 znakov zmesti cely.
    'log.hr_breathing_triggered': {
        'sk': 'Tep {bpm} BPM — záťaž drží hore',
        'en': 'Heart rate {bpm} BPM — load holding up',
        'ja': '心拍 {bpm} BPM — 負荷が高いまま続いています',
        'zh': '心率 {bpm} BPM — 负荷持续偏高',
        'ru': 'Пульс {bpm} BPM — нагрузка держится высокой',
        'es': 'Pulso {bpm} BPM — la carga se mantiene alta',
        'de': 'Puls {bpm} BPM — die Last bleibt oben',
        'fr': 'Pouls {bpm} BPM — la charge reste haute',
        'pt': 'Pulso {bpm} BPM — a carga se mantém alta',
    },
    'log.hr_bind_fallback': {
        'sk': 'Adresu {ip} toto PC nemá — počúvam tep na všetkých sieťach. Ak to funguje, pokojne si v poli nechaj 0.0.0.0.',
        'en': 'This PC does not have the address {ip} - listening for heart rate on all networks instead. If it works, just leave 0.0.0.0 in the field.',
        'ja': 'このPCには {ip} というアドレスがありません - 代わりにすべてのネットワークで心拍を待ち受けます。動作する場合は、欄に 0.0.0.0 のままにしておいてください。',
        'zh': '此电脑没有 {ip} 这个地址 - 改为在所有网络上监听心率。如果可用，字段中保留 0.0.0.0 即可。',
        'ru': 'У этого ПК нет адреса {ip} - слушаю пульс во всех сетях. Если работает, просто оставьте в поле 0.0.0.0.',
        'es': 'Este PC no tiene la dirección {ip} - escuchando el ritmo cardíaco en todas las redes. Si funciona, deja 0.0.0.0 en el campo.',
        'de': 'Dieser PC hat die Adresse {ip} nicht - lausche stattdessen auf allen Netzwerken. Wenn es funktioniert, lass einfach 0.0.0.0 im Feld stehen.',
        'fr': "Ce PC n'a pas l'adresse {ip} - écoute du rythme cardiaque sur tous les réseaux. Si ça marche, laisse simplement 0.0.0.0 dans le champ.",
        'pt': 'Este PC não tem o endereço {ip} - ouvindo a frequência cardíaca em todas as redes. Se funcionar, deixe 0.0.0.0 no campo.',
    },
    'log.hr_overlay_disabled': {
        'sk': 'V okne „Vizuály v hre“ máš vypnuté všetky vizuály — bez nich ti appka hlášku nepošle. Ak chceš, aby sa ozývala, zapni si aspoň jeden.',
        'en': 'Every visual is switched off in “Visuals in game” — without one the app will not give you a cue. Switch at least one on if you want it to speak up.',
        'ja': '「ゲーム中のビジュアル」ウィンドウで、ビジュアルがすべてオフになっています — ひとつもないと、アプリは合図を出せません。合図がほしいなら、少なくともひとつオンにしてください。',
        'zh': '你在“游戏中的视觉效果”窗口里关掉了所有视觉效果——没有它们，应用就不会给你发提示。如果希望它出声提醒你，请至少打开一个。',
        'ru': 'В окне «Визуалы в игре» у тебя выключены все визуалы — без них приложение не подаст тебе подсказку. Если хочешь, чтобы оно давало о себе знать, включи хотя бы один.',
        'es': 'En la ventana «Visuales en el juego» tienes apagados todos los visuales — sin ellos la app no te enviará ningún aviso. Si quieres que te avise, activa al menos uno.',
        'de': 'Im Fenster „Visuals im Spiel“ hast du alle Visuals ausgeschaltet — ohne sie schickt dir die App keinen Hinweis. Wenn du willst, dass sie sich meldet, schalte mindestens eins ein.',
        'fr': 'Dans la fenêtre « Visuels en jeu », tous les visuels sont désactivés — sans eux, l’app ne t’enverra aucun rappel. Si tu veux qu’elle se manifeste, actives-en au moins un.',
        'pt': 'Na janela “Visuais no jogo” todos os visuais estão desativados — sem eles o app não te manda nenhum aviso. Se quiser receber avisos, ative pelo menos um.',
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
    # Uz nie "Anti-Cheat Safe Mode": zaruku voci anti-cheatu moze dat len
    # jeho vyrobca, a "ziadne blokovanie" nebola pravda - skratku "teraz nie"
    # si appka registruje (`hotkey.py`, RegisterHotKey), takze tu kombinaciu
    # hra nedostane. Skratka sa da zmenit (alebo vypnut) v subore nastaveni,
    # preto veta hovori o skratke "teraz nie" a Ctrl+Alt+Z len ako predvolbe.
    'log.safe_mode': {
        'sk': 'Vedľa hry: vstupy sa len pasívne čítajú (žiadna simulácia stlačení). Jediná výnimka je skratka „teraz nie“ (predvolene Ctrl+Alt+Z), ktorú si Zanshin rezervuje pre seba.',
        'en': 'Next to the game: input is only read passively (no simulated key or mouse presses). The one exception is the “not now” shortcut (Ctrl+Alt+Z by default), which Zanshin reserves for itself.',
        'ja': 'ゲームのそばで：入力は受動的に読み取るだけです（キーやマウスの押下をシミュレートすることはありません）。唯一の例外は「今はいい」のショートカット（既定は Ctrl+Alt+Z）で、Zanshin が自分用に確保しています。',
        'zh': '在游戏旁运行：只被动读取输入（不模拟任何按键或鼠标点击）。唯一的例外是“现在不要”快捷键（默认 Ctrl+Alt+Z），Zanshin 把它留给自己用。',
        'ru': 'Рядом с игрой: ввод только пассивно считывается (никакой имитации нажатий клавиш или мыши). Единственное исключение — сочетание «не сейчас» (по умолчанию Ctrl+Alt+Z), которое Zanshin резервирует за собой.',
        'es': 'Junto al juego: la entrada solo se lee de forma pasiva (sin simular pulsaciones de teclas ni del ratón). La única excepción es el atajo «ahora no» (Ctrl+Alt+Z por defecto), que Zanshin se reserva para sí.',
        'de': 'Neben dem Spiel: Eingaben werden nur passiv gelesen (keine simulierten Tasten- oder Mausklicks). Die einzige Ausnahme ist das Tastenkürzel „Jetzt nicht“ (standardmäßig Ctrl+Alt+Z), das Zanshin für sich reserviert.',
        'fr': 'À côté du jeu : les entrées ne sont lues que passivement (aucune simulation de touches ni de clics souris). La seule exception est le raccourci « pas maintenant » (Ctrl+Alt+Z par défaut), que Zanshin se réserve.',
        'pt': 'Ao lado do jogo: a entrada é lida apenas de forma passiva (sem simular teclas nem cliques do mouse). A única exceção é o atalho “agora não” (Ctrl+Alt+Z por padrão), que o Zanshin reserva para si.',
    },
    'session.summary': {
        'sk': 'Relácia: Ťažisko {g}× | Čeľusť {j}× | Uvoľnenie {r}× | Dych {b}×',
        'en': 'Session: Grounding {g}× | Jaw {j}× | Release {r}× | Breath {b}×',
        'ja': 'セッション: 重心 {g}× | 顎 {j}× | 解放 {r}× | 呼吸 {b}×',
        'zh': '本局：重心 {g}次 | 下颌 {j}次 | 放松 {r}次 | 呼吸 {b}次',
        'ru': 'Сессия: Опора {g}× | Челюсть {j}× | Отпусти {r}× | Дыхание {b}×',
        'es': 'Sesión: Apoyo {g}× | Mandíbula {j}× | Suelta {r}× | Respiración {b}×',
        'de': 'Sitzung: Erdung {g}× | Kiefer {j}× | Loslassen {r}× | Atem {b}×',
        'fr': 'Session : Ancrage {g}× | Mâchoire {j}× | Relâche {r}× | Respiration {b}×',
        'pt': 'Sessão: Aterramento {g}× | Mandíbula {j}× | Solta {r}× | Respiração {b}×',
    },
    'slots.title': {
        'sk': 'Sloty spúšťačov',
        'en': 'Trigger slots',
        'ja': 'トリガー・スロット',
        'zh': '触发插槽',
        'ru': 'Слоты триггеров',
        'es': 'Slots de disparadores',
        'de': 'Trigger-Slots',
        'fr': 'Slots de déclencheurs',
        'pt': 'Slots de gatilho',
    },
    'slots.hint': {
        'sk': 'Viac slotov môže mať aj rovnaký kláves — spustia sa všetky. Kombinácia prehrá hlas aj zvukový efekt naraz.',
        'en': 'Several slots can share the same key - all of them will fire. Combo mode plays the voice and the sound effect together.',
        'ja': '複数のスロットに同じキーを割り当てることもできます - すべて同時に発動します。コンビネーションは音声と効果音を同時に再生します。',
        'zh': '多个插槽可以共用同一个按键 - 它们会同时触发。组合模式会同时播放语音和音效。',
        'ru': 'Несколько слотов могут использовать одну и ту же клавишу - все они сработают вместе. Комбо-режим воспроизводит голос и звуковой эффект одновременно.',
        'es': 'Varios slots pueden compartir la misma tecla - todos se activarán. El modo Combo reproduce la voz y el efecto de sonido juntos.',
        'de': 'Mehrere Slots können sich dieselbe Taste teilen - sie alle lösen dann aus. Der Kombo-Modus spielt Stimme und Soundeffekt gemeinsam ab.',
        'fr': "Plusieurs slots peuvent partager la même touche - ils se déclenchent tous ensemble. Le mode Combo joue la voix et l'effet sonore en même temps.",
        'pt': 'Vários slots podem compartilhar a mesma tecla - todos serão acionados juntos. O modo Combo toca a voz e o efeito sonoro ao mesmo tempo.',
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
        'sk': 'Pripraviť hlásky',
        'en': 'Prepare voice lines',
        'ja': '音声を準備',
        'zh': '准备语音条目',
        'ru': 'Подготовить голосовые фразы',
        'es': 'Preparar frases de voz',
        'de': 'Sprachzeilen vorbereiten',
        'fr': 'Préparer les répliques vocales',
        'pt': 'Preparar falas de voz',
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
        'sk': 'Log',
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
        'sk': 'Text hlášky (napr. Grounded)...',
        'en': 'Voice line text (e.g. Grounded)...',
        'ja': 'セリフのテキスト（例：Grounded）...',
        'zh': '语音文本（例如 "落地"）…',
        'ru': 'Текст голосовой фразы (например, «Опора»)…',
        'es': 'Texto de la frase de voz (ej. Con los pies en la tierra)...',
        'de': 'Text der Sprachzeile (z. B. Geerdet) ...',
        'fr': 'Texte de la réplique vocale (ex. Ancré)...',
        'pt': 'Texto da fala de voz (ex.: Aterrado)...',
    },
    'key.mouse_prefix': {
        'sk': 'myš: {key}',
        'en': 'mouse: {key}',
        'ja': 'マウス: {key}',
        'zh': '鼠标: {key}',
        'ru': 'мышь: {key}',
        'es': 'ratón: {key}',
        'de': 'Maus: {key}',
        'fr': 'souris : {key}',
        'pt': 'mouse: {key}',
    },
    'key.gamepad_prefix': {
        'sk': '🎮 {key}',
        'en': '🎮 {key}',
        'ja': '🎮 {key}',
        'zh': '🎮 {key}',
        'ru': '🎮 {key}',
        'es': '🎮 {key}',
        'de': '🎮 {key}',
        'fr': '🎮 {key}',
        'pt': '🎮 {key}',
    },
    'slots.gamepad_hint': {
        'sk': 'Gamepad (Xbox aj PlayStation): A=✕  B=○  X=□  Y=△  LB=L1  RB=R1  LT=L2  RT=R2.',
        'en': 'Gamepad (Xbox and PlayStation): A=✕  B=○  X=□  Y=△  LB=L1  RB=R1  LT=L2  RT=R2.',
        'ja': 'ゲームパッド（Xbox・PlayStation対応）: A=✕  B=○  X=□  Y=△  LB=L1  RB=R1  LT=L2  RT=R2。',
        'zh': '手柄（Xbox 及 PlayStation）：A=✕  B=○  X=□  Y=△  LB=L1  RB=R1  LT=L2  RT=R2。',
        'ru': 'Геймпад (Xbox и PlayStation): A=✕  B=○  X=□  Y=△  LB=L1  RB=R1  LT=L2  RT=R2.',
        'es': 'Mando (Xbox y PlayStation): A=✕  B=○  X=□  Y=△  LB=L1  RB=R1  LT=L2  RT=R2.',
        'de': 'Gamepad (Xbox und PlayStation): A=✕  B=○  X=□  Y=△  LB=L1  RB=R1  LT=L2  RT=R2.',
        'fr': 'Manette (Xbox et PlayStation) : A=✕  B=○  X=□  Y=△  LB=L1  RB=R1  LT=L2  RT=R2.',
        'pt': 'Controle (Xbox e PlayStation): A=✕  B=○  X=□  Y=△  LB=L1  RB=R1  LT=L2  RT=R2.',
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
        'sk': '🔄  Automaticky (podľa témy)',
        'en': '🔄  Automatic (matches theme)',
        'ja': '🔄  自動（テーマに合わせる）',
        'zh': '🔄  自动（匹配主题）',
        'ru': '🔄  Автоматически (соответствует теме)',
        'es': '🔄  Automático (según el tema)',
        'de': '🔄  Automatisch (passend zum Theme)',
        'fr': '🔄  Automatique (selon le thème)',
        'pt': '🔄  Automático (conforme o tema)',
    },
    'sfx.custom_prefix': {
        'sk': '📁  Vlastný súbor: {name}',
        'en': '📁  Custom file: {name}',
        'ja': '📁  カスタムファイル: {name}',
        'zh': '📁  自定义文件：{name}',
        'ru': '📁  Свой файл: {name}',
        'es': '📁  Archivo personalizado: {name}',
        'de': '📁  Eigene Datei: {name}',
        'fr': '📁  Fichier personnalisé : {name}',
        'pt': '📁  Arquivo personalizado: {name}',
    },
    'pack.zen': {
        'sk': '🌿 Zen',
        'en': '🌿 Zen',
        'ja': '🌿 禅',
        'zh': '🌿 禅意',
        'ru': '🌿 Дзен',
        'es': '🌿 Zen',
        'de': '🌿 Zen',
        'fr': '🌿 Zen',
        'pt': '🌿 Zen',
    },
    'pack.modern': {
        'sk': '⚡ Modern',
        'en': '⚡ Modern',
        'ja': '⚡ モダン',
        'zh': '⚡ 现代',
        'ru': '⚡ Модерн',
        'es': '⚡ Moderno',
        'de': '⚡ Modern',
        'fr': '⚡ Moderne',
        'pt': '⚡ Moderno',
    },
    'slot.summary_default': {
        'sk': 'predvolené nastavenie',
        'en': 'default settings',
        'ja': '初期設定のまま',
        'zh': '默认设置',
        'ru': 'стандартные настройки',
        'es': 'configuración predeterminada',
        'de': 'Standardeinstellungen',
        'fr': 'réglages par défaut',
        'pt': 'configurações padrão',
    },
    'slot.summary_every': {
        'sk': 'každé {n}.',
        'en': 'every {n}.',
        'ja': '{n}回ごと',
        'zh': '每 {n} 次',
        'ru': 'каждое {n}-е',
        'es': 'cada {n}',
        'de': 'jedes {n}. Mal',
        'fr': 'tous les {n}',
        'pt': 'a cada {n}',
    },
    'dialog.slot_settings_title': {
        'sk': 'Slot {n} — podrobné nastavenie',
        'en': 'Slot {n} - detailed settings',
        'ja': 'スロット {n} - 詳細設定',
        'zh': '插槽 {n} - 详细设置',
        'ru': 'Слот {n} - подробные настройки',
        'es': 'Slot {n} - configuración detallada',
        'de': 'Slot {n} - Detaileinstellungen',
        'fr': 'Slot {n} - réglages détaillés',
        'pt': 'Slot {n} - configurações detalhadas',
    },
    'dialog.voice_label': {
        'sk': 'Hlas pre tento slot:',
        'en': 'Voice for this slot:',
        'ja': 'このスロットの音声:',
        'zh': '该插槽使用的语音：',
        'ru': 'Голос для этого слота:',
        'es': 'Voz para este slot:',
        'de': 'Stimme für diesen Slot:',
        'fr': 'Voix pour ce slot :',
        'pt': 'Voz para este slot:',
    },
    'dialog.voice_note': {
        'sk': 'Kedy sa appka ozve, riadi záťaž tela — nie je to nastavenie, hranicu si appka počíta z tvojich relácií. S čím práve počíta, vidíš hore na stránke Spúšťače.',
        'en': 'When the app speaks is driven by your body load — it is not a setting; the app computes its threshold from your sessions. What it is using right now is shown at the top of the Triggers page.',
        'ja': 'アプリがいつ声をかけるかは、体の負荷で決まります — これは設定ではなく、しきい値はアプリがあなたのセッションから算出します。今どの値を使っているかは、「トリガー」ページの上部で確認できます。',
        'zh': '应用什么时候出声，由身体的负荷决定——这不是一项设置，阈值是应用根据你的记录算出来的。它当前用的数值，可以在“触发器”页面顶部看到。',
        'ru': 'Когда приложение подаёт голос, определяет нагрузка тела — это не настройка, порог приложение вычисляет по твоим сессиям. С какими числами оно считает прямо сейчас, видно вверху страницы «Триггеры».',
        'es': 'Cuándo habla la app lo decide la carga del cuerpo — no es un ajuste: el umbral lo calcula la app a partir de tus sesiones. Con qué valores cuenta ahora mismo lo ves arriba, en la página Disparadores.',
        'de': 'Wann sich die App meldet, bestimmt die Last deines Körpers — das ist keine Einstellung, die Schwelle berechnet die App aus deinen Sitzungen. Womit sie gerade rechnet, siehst du oben auf der Seite Trigger.',
        'fr': 'Le moment où l’app se manifeste dépend de la charge de ton corps — ce n’est pas un réglage, l’app calcule son seuil à partir de tes séances. Ce qu’elle utilise en ce moment, tu le vois en haut de la page Déclencheurs.',
        'pt': 'Quando o app avisa depende da carga do seu corpo — não é uma configuração; o app calcula o limiar a partir das suas sessões. O que ele está usando agora aparece no topo da página Gatilhos.',
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
        'zh': '无 — 使用语音（TTS）。',
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
        'sk': 'Zvukový súbor s hlasom pre slot {n}',
        'en': 'Voice sound file for slot {n}',
        'ja': 'スロット {n} の音声ファイル（声）',
        'zh': '插槽 {n} 的语音声音文件',
        'ru': 'Звуковой файл голоса для слота {n}',
        'es': 'Archivo de voz para el slot {n}',
        'de': 'Sprach-Audiodatei für Slot {n}',
        'fr': 'Fichier audio de voix pour le slot {n}',
        'pt': 'Arquivo de áudio de voz para o slot {n}',
    },
    'log.slot_voice_saved': {
        'sk': 'Slot {n}: hlas = {voice}',
        'en': 'Slot {n}: voice = {voice}',
        'ja': 'スロット {n}: 音声 = {voice}',
        'zh': '插槽 {n}：语音 = {voice}',
        'ru': 'Слот {n}: голос = {voice}',
        'es': 'Slot {n}: voz = {voice}',
        'de': 'Slot {n}: Stimme = {voice}',
        'fr': 'Slot {n} : voix = {voice}',
        'pt': 'Slot {n}: voz = {voice}',
    },
    'log.slot_voice_recorded': {
        'sk': 'Slot {n}: vlastný hlas nahraný',
        'en': 'Slot {n}: own voice recorded',
        'ja': 'スロット {n}: 自分の声を録音しました',
        'zh': '插槽 {n}：已录制自己的声音',
        'ru': 'Слот {n}: свой голос записан',
        'es': 'Slot {n}: voz propia grabada',
        'de': 'Slot {n}: eigene Stimme aufgenommen',
        'fr': 'Slot {n} : voix propre enregistrée',
        'pt': 'Slot {n}: voz própria gravada',
    },
    'log.slot_voice_set': {
        'sk': 'Slot {n}: vlastný hlas zo súboru ({name})',
        'en': 'Slot {n}: own voice from file ({name})',
        'ja': 'スロット {n}: ファイルから声を設定 ({name})',
        'zh': '插槽 {n}：从文件设置声音（{name}）',
        'ru': 'Слот {n}: свой голос из файла ({name})',
        'es': 'Slot {n}: voz propia desde archivo ({name})',
        'de': 'Slot {n}: eigene Stimme aus Datei ({name})',
        'fr': 'Slot {n} : voix propre depuis un fichier ({name})',
        'pt': 'Slot {n}: voz própria de um arquivo ({name})',
    },
    'log.slot_voice_cleared': {
        'sk': 'Slot {n}: vlastný hlas zrušený → TTS',
        'en': 'Slot {n}: own voice cleared → TTS',
        'ja': 'スロット {n}: 自分の声を解除 → TTS',
        'zh': '插槽 {n}：已清除自己的声音 → TTS',
        'ru': 'Слот {n}: свой голос убран → TTS',
        'es': 'Slot {n}: voz propia quitada → TTS',
        'de': 'Slot {n}: eigene Stimme entfernt → TTS',
        'fr': 'Slot {n} : voix propre retirée → TTS',
        'pt': 'Slot {n}: voz própria removida → TTS',
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
    'log.cue_rate_changed': {
        'sk': 'Ako často sa ozvem: {volba}',
        'en': 'Cue frequency: {volba}',
        'ja': '話しかける頻度: {volba}',
        'zh': '提示频率：{volba}',
        'ru': 'Частота реплик: {volba}',
        'es': 'Frecuencia de señales: {volba}',
        'de': 'Hinweis-Häufigkeit: {volba}',
        'fr': 'Fréquence des phrases : {volba}',
        'pt': 'Frequência dos avisos: {volba}',
    },
    'log.vizualy_napravene': {
        'sk': 'Zapla som in-game vizuály — bez aspoň jedného sa appka nemá ako ozvať. Vypnúť ich vieš na stránke „V hre“ v paneli „Vizuály v hre“.',
        'en': 'I turned the in-game visuals on — without at least one the app cannot speak at all. You can turn them off on the “In-game” page, in the “Visuals in game” panel.',
        'ja': 'ゲーム中のビジュアルをオンにしました — ひとつもないと、アプリはまったく合図を出せません。オフにしたいときは、「ゲーム中」ページの「ゲーム中のビジュアル」パネルでできます。',
        'zh': '我打开了游戏内视觉效果——至少要有一个，应用才有办法出声提醒。要关掉它们，可以去“游戏中”页面的“游戏中的视觉效果”面板。',
        'ru': 'Я включила визуалы в игре — если не включён ни один, приложению нечем дать о себе знать. Выключить их можно на странице «В игре», в панели «Визуалы в игре».',
        'es': 'He activado los visuales en el juego — sin al menos uno, la app no tiene cómo avisarte. Puedes apagarlos en la página «En el juego», en el panel «Visuales en el juego».',
        'de': 'Ich habe die In-Game-Visuals eingeschaltet — ohne mindestens eins kann sich die App gar nicht melden. Ausschalten kannst du sie auf der Seite „Im Spiel“ im Panel „Visuals im Spiel“.',
        'fr': 'J’ai activé les visuels en jeu — sans au moins l’un d’eux, l’app n’a aucun moyen de se manifester. Tu peux les désactiver sur la page « En jeu », dans le panneau « Visuels en jeu ».',
        'pt': 'Ativei os visuais no jogo — sem pelo menos um, o app não tem como avisar. Você pode desativá-los na página “No jogo”, no painel “Visuais no jogo”.',
    },
    'log.overlay_test_ukonceny': {
        'sk': 'Ukončila som test vizuálu — kým beží, pohlcuje kliky myšou nad hrou.',
        'en': 'I ended the visual test — while it runs it swallows mouse clicks over the game.',
        'ja': 'ビジュアルのテストを終了しました。実行中はゲーム上のクリックを奪います。',
        'zh': '我结束了视觉测试——测试运行时会吞掉游戏上的鼠标点击。',
        'ru': 'Я завершила тест визуала — пока он идёт, он перехватывает клики мышью поверх игры.',
        'es': 'He terminado la prueba del visual — mientras está en marcha, se traga los clics del ratón sobre el juego.',
        'de': 'Ich habe den Visual-Test beendet — solange er läuft, schluckt er Mausklicks über dem Spiel.',
        'fr': 'J’ai arrêté le test du visuel — tant qu’il tourne, il avale les clics de souris au-dessus du jeu.',
        'pt': 'Terminei o teste do visual — enquanto está rodando, ele engole os cliques do mouse sobre o jogo.',
    },
    'palette.slot': {
        'sk': 'Hláška — {label}',
        'en': 'Cue — {label}',
        'ja': 'セリフ — {label}',
        'zh': '提示语 — {label}',
        'ru': 'Реплика — {label}',
        'es': 'Aviso — {label}',
        'de': 'Hinweis — {label}',
        'fr': 'Rappel — {label}',
        'pt': 'Aviso — {label}',
    },
    'slots.unnamed': {
        'sk': 'Hláška {n}',
        'en': 'Cue {n}',
        'ja': 'セリフ {n}',
        'zh': '提示语 {n}',
        'ru': 'Реплика {n}',
        'es': 'Aviso {n}',
        'de': 'Hinweis {n}',
        'fr': 'Rappel {n}',
        'pt': 'Aviso {n}',
    },
    'kamae.no_watch': {
        'sk': 'Počúvam, ale nemám tep',
        'en': 'Listening, but no heart rate',
        'ja': '待機中ですが心拍がありません',
        'zh': '在听，但没有心率',
        'ru': 'Слушаю, но пульса нет',
        'es': 'Escuchando, pero sin pulso',
        'de': 'Ich höre zu, aber ohne Puls',
        'fr': "J'écoute, mais je n'ai pas de pouls",
        'pt': 'Ouvindo, mas sem pulso',
    },
    'kamae.no_watch_sub': {
        'sk': 'Bez hodiniek neviem, kedy ti záťaž stúpa — ozvať sa nemám ako. Na stránke „V hre“ zapni „Počúvať tep z hodiniek“.',
        'en': 'Without a watch I cannot tell when your load rises — I have no way to speak up. Turn on “Listen for heart rate from the watch” on the “In-game” page.',
        'ja': '時計がないと、負荷が上がったことがわかりません — 声をかけようがありません。「ゲーム中」ページで「時計から心拍を受け取る」をオンにしてください。',
        'zh': '没有手表，我就不知道你的负荷什么时候升高——也就没办法出声。请在“游戏中”页面打开“接收手表的心率”。',
        'ru': 'Без часов я не знаю, когда растёт твоя нагрузка, — так что подать голос я не могу. На странице «В игре» включи «Слушать пульс с часов».',
        'es': 'Sin reloj no sé cuándo te sube la carga — no tengo cómo avisarte. En la página «En el juego», activa «Escuchar el pulso del reloj».',
        'de': 'Ohne Uhr weiß ich nicht, wann deine Last steigt — ich habe keine Möglichkeit, mich zu melden. Schalte auf der Seite „Im Spiel“ „Puls von der Uhr empfangen“ ein.',
        'fr': 'Sans montre, je ne sais pas quand ta charge monte — je n’ai aucun moyen de me manifester. Sur la page « En jeu », active « Écouter le pouls de la montre ».',
        'pt': 'Sem relógio, não sei quando a sua carga sobe — não tenho como avisar. Na página “No jogo”, ative “Ouvir o pulso do relógio”.',
    },
    # Senzor POCUVA, ale tep nechodi (vypadok, obsadeny port, este sa nic
    # nepripojilo). Odlisene od `kamae.no_watch`, co je vypnuty senzor.
    # Pas doteraz v tomto stave klamal "Sledujem tep a cakam..." len podla
    # prepinaca - najvacsi prvok okna tvrdil nepravdu (bug A2).
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
    # 0.2: tep ide hodinky -> telefon (Bluetooth) -> Wi-Fi -> pocitac, nie
    # z hodiniek rovno na Wi-Fi. Stare preklady (_DOPLNENE_PREKLADY) zmazane,
    # aby stare znenie neprezilo v ziadnom jazyku; nove su z fazy jazykov.
    'kamae.no_hr_sub': {
        'sk': 'Senzor počúva, ale z hodiniek zatiaľ nič nechodí. Skontroluj, či hodinky merajú a sú pri telefóne (Bluetooth) a či je telefón na tej istej Wi‑Fi ako počítač.',
        'en': 'The sensor is listening, but nothing is coming from the watch yet. Check that the watch is measuring and near the phone (Bluetooth), and that the phone is on the same Wi‑Fi as the PC.',
        'ja': 'センサーは待ち受けていますが、時計からまだ何も届いていません。時計が計測中で電話の近くにあるか（Bluetooth）、電話が PC と同じ Wi‑Fi につながっているかを確認してください。',
        'zh': '传感器在监听，但手表那边还没有任何数据过来。检查手表是否在测量、是否在手机旁边（蓝牙），以及手机和电脑是否连在同一个 Wi‑Fi 上。',
        'ru': 'Датчик слушает, но с часов пока ничего не приходит. Проверь, что часы измеряют и находятся рядом с телефоном (Bluetooth) и что телефон в той же сети Wi‑Fi, что и компьютер.',
        'es': 'El sensor escucha, pero del reloj todavía no llega nada. Comprueba que el reloj esté midiendo y cerca del móvil (Bluetooth), y que el móvil esté en el mismo Wi‑Fi que el PC.',
        'de': 'Der Sensor hört zu, aber von der Uhr kommt noch nichts an. Prüfe, ob die Uhr misst und beim Handy ist (Bluetooth) und ob das Handy im selben WLAN ist wie der PC.',
        'fr': 'Le capteur écoute, mais rien n’arrive encore de la montre. Vérifie que la montre mesure et qu’elle est près du téléphone (Bluetooth), et que le téléphone est sur le même Wi‑Fi que l’ordinateur.',
        'pt': 'O sensor está ouvindo, mas nada chegou do relógio ainda. Verifique se o relógio está medindo e perto do celular (Bluetooth) e se o celular está no mesmo Wi‑Fi que o PC.',
    },
    'dev.min_gap_clamped': {
        'sk': 'Odstup som zdvihla na {s} s — nižšie by si dve hlášky zneplatnili meracie okná.',
        'en': 'I raised the gap to {s} s — below that two cues invalidate each other’s measurement windows.',
        'ja': '間隔を {s} 秒に引き上げました。これより短いと2つのセリフが互いの測定窓を無効にします。',
        'zh': '我把间隔提高到 {s} 秒——再短两条提示会互相作废测量窗口。',
        'ru': 'Я подняла интервал до {s} с — ниже две подсказки обнуляли бы измерительные окна друг друга.',
        'es': 'He subido el intervalo a {s} s — por debajo, dos avisos invalidarían mutuamente sus ventanas de medición.',
        'de': 'Ich habe den Abstand auf {s} s angehoben — darunter entwerten zwei Hinweise ihre Messfenster gegenseitig.',
        'fr': 'J’ai remonté l’écart à {s} s — en dessous, deux rappels invalideraient mutuellement leurs fenêtres de mesure.',
        'pt': 'Subi o intervalo para {s} s — abaixo disso, dois avisos invalidam as janelas de medição um do outro.',
    },
    'log.cue_skipped_all_off': {
        'sk': 'Chvíľa na hlášku prišla, ale všetky sú vypnuté — mlčím.',
        'en': 'The moment for a cue came, but all of them are off — staying silent.',
        'ja': 'セリフの頃合いでしたが、すべてオフなので黙っています。',
        'zh': '到了该出声的时候，但所有提示都已关闭——保持安静。',
        'ru': 'Момент для реплики настал, но все они выключены — молчу.',
        'es': 'Llegó el momento de un aviso, pero están todos apagados: me callo.',
        'de': 'Der Moment für einen Hinweis war da, aber alle sind aus — ich schweige.',
        'fr': "Le moment d'un rappel est venu, mais ils sont tous désactivés — je me tais.",
        'pt': 'Chegou o momento de um aviso, mas estão todos desligados — fico calada.',
    },
    'log.hr_port_busy_retry': {
        'sk': 'Port {port} drží iný program — skúšam znova ({n}/{z}). Býva to druhá spustená kópia appky.',
        'en': 'Port {port} is held by another program — retrying ({n}/{z}). Usually a second copy of the app.',
        'ja': 'ポート {port} は別のプログラムが使用中です。再試行します（{n}/{z}）。たいていはアプリの二重起動です。',
        'zh': '端口 {port} 被其他程序占用——正在重试（{n}/{z}）。通常是应用开了第二个副本。',
        'ru': 'Порт {port} занят другой программой — пробую снова ({n}/{z}). Обычно это вторая копия приложения.',
        'es': 'El puerto {port} lo tiene otro programa: reintentando ({n}/{z}). Suele ser una segunda copia de la app.',
        'de': 'Port {port} ist von einem anderen Programm belegt — neuer Versuch ({n}/{z}). Meist eine zweite Kopie der App.',
        'fr': "Le port {port} est occupé par un autre programme — nouvel essai ({n}/{z}). C'est souvent une seconde copie de l'app.",
        'pt': 'A porta {port} está ocupada por outro programa — tentando de novo ({n}/{z}). Costuma ser uma segunda cópia do app.',
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
    # Pocuvame, ale za ~20 s sa nikto nepripojil (najcastejsie firewall alebo
    # ina Wi-Fi). Iny problem nez "Pripaja sa…", tak to aj hovori (B2).
    'settings.hr_status_no_client': {
        'sk': 'Počúvam, ale nikto sa nepripojil',
        'en': 'Listening, but nobody connected',
        'ja': 'Listening, but nobody connected',
        'zh': 'Listening, but nobody connected',
        'ru': 'Listening, but nobody connected',
        'es': 'Listening, but nobody connected',
        'de': 'Listening, but nobody connected',
        'fr': 'Listening, but nobody connected',
        'pt': 'Listening, but nobody connected',
    },
    # Po vycerpani pokusov sa senzor VZDAL. Doteraz stav ostal "busy" a
    # stitok navzdy tvrdil "skusam znova", hoci to uz nikto neskusa (B3).
    'settings.hr_status_busy_gave_up': {
        'sk': 'Port je obsadený — senzor vypnutý',
        'en': 'Port is busy — sensor turned off',
        'ja': 'Port is busy — sensor turned off',
        'zh': 'Port is busy — sensor turned off',
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
        'sk': 'jedol som pred hraním',
        'en': 'ate before playing',
        'ja': 'プレイ前に食事',
        'zh': '玩之前吃过东西',
        'ru': 'ел перед игрой',
        'es': 'comí antes de jugar',
        'de': 'vor dem Spielen gegessen',
        'fr': "j'ai mangé avant de jouer",
        'pt': 'comi antes de jogar',
    },
    'session.end.trace_hint': {
        'sk': 'Tep za celý večer. Trojuholníky sú hlášky, tenký pruh nad pásmami ukazuje, kde si mal ruky na klávesnici — teda kde sa pravdepodobne hralo.',
        'en': 'Your heart rate for the whole evening. Triangles are cues; the thin band above the zones shows where your hands were on the keyboard — so probably where you were playing.',
        'ja': '一晩の心拍です。三角はセリフ、ゾーンの上の細い帯は手がキーボードにあった時間 — つまりおそらくプレイ中の時間です。',
        'zh': '整晚的心率。三角形是提示语，色带上方的细条表示你的手在键盘上的时间——也就是大概在游戏中的时间。',
        'ru': 'Пульс за весь вечер. Треугольники — реплики, тонкая полоса над зонами показывает, где руки были на клавиатуре, то есть где ты, скорее всего, играл.',
        'es': 'Tu pulso de toda la noche. Los triángulos son los avisos; la banda fina sobre las zonas muestra dónde tenías las manos en el teclado, o sea dónde probablemente jugabas.',
        'de': 'Dein Puls für den ganzen Abend. Dreiecke sind Hinweise; das schmale Band über den Zonen zeigt, wo deine Hände auf der Tastatur waren — also wo du vermutlich gespielt hast.',
        'fr': 'Ton pouls pour toute la soirée. Les triangles sont les rappels ; la fine bande au-dessus des zones montre où tes mains étaient sur le clavier, donc probablement où tu jouais.',
        'pt': 'O seu pulso da noite toda. Os triângulos são os avisos; a faixa fina acima das zonas mostra onde você estava com as mãos no teclado — ou seja, onde provavelmente estava jogando.',
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
    'dialog.timing_title': {
        'sk': 'Časovanie',
        'en': 'Timing',
        'ja': 'タイミング',
        'zh': '时间设置',
        'ru': 'Тайминг',
        'es': 'Tiempos',
        'de': 'Timing',
        'fr': 'Minutage',
        'pt': 'Tempo',
    },
    'dialog.custom_cooldown': {
        'sk': 'Vlastný cooldown (s):',
        'en': 'Custom cooldown (s):',
        'ja': 'カスタムクールダウン（秒）:',
        'zh': '自定义冷却时间（秒）：',
        'ru': 'Свой кулдаун (с):',
        'es': 'Cooldown personalizado (s):',
        'de': 'Eigener Cooldown (s):',
        'fr': 'Cooldown personnalisé (s) :',
        'pt': 'Cooldown personalizado (s):',
    },
    'dialog.delay': {
        'sk': 'Oneskorenie pred hláskou (s):',
        'en': 'Delay before line (s):',
        'ja': 'セリフ再生までの遅延（秒）:',
        'zh': '播放前延迟（秒）：',
        'ru': 'Задержка перед фразой (с):',
        'es': 'Retraso antes de la frase (s):',
        'de': 'Verzögerung vor der Zeile (s):',
        'fr': 'Délai avant la réplique (s) :',
        'pt': 'Atraso antes da fala (s):',
    },
    'dialog.every_n': {
        'sk': 'Spustí sa každé N-té stlačenie:',
        'en': 'Fires every Nth press:',
        'ja': '何回押すごとに発動するか:',
        'zh': '每第 N 次按下触发：',
        'ru': 'Срабатывает каждое N-е нажатие:',
        'es': 'Se activa cada N pulsaciones:',
        'de': 'Löst jeden N-ten Tastendruck aus:',
        'fr': 'Se déclenche tous les N appuis :',
        'pt': 'Aciona a cada N-ésimo toque:',
    },
    'dialog.repeat': {
        'sk': 'Počet opakovaní:',
        'en': 'Repeat count:',
        'ja': '繰り返し回数:',
        'zh': '重复次数：',
        'ru': 'Количество повторов:',
        'es': 'Número de repeticiones:',
        'de': 'Anzahl Wiederholungen:',
        'fr': 'Nombre de répétitions :',
        'pt': 'Número de repetições:',
    },
    'dialog.repeat_gap': {
        'sk': 'Pauza medzi opakovaniami (s):',
        'en': 'Gap between repeats (s):',
        'ja': '繰り返し間の間隔（秒）:',
        'zh': '重复间隔（秒）：',
        'ru': 'Пауза между повторами (с):',
        'es': 'Pausa entre repeticiones (s):',
        'de': 'Pause zwischen Wiederholungen (s):',
        'fr': 'Pause entre les répétitions (s) :',
        'pt': 'Pausa entre repetições (s):',
    },
    'dialog.jitter': {
        'sk': 'Náhodné rozptýlenie cooldownu (%):',
        'en': 'Random cooldown jitter (%):',
        'ja': 'クールダウンのランダムなばらつき（%）:',
        'zh': '冷却时间随机浮动（%）：',
        'ru': 'Случайный разброс кулдауна (%):',
        'es': 'Variación aleatoria del cooldown (%):',
        'de': 'Zufällige Cooldown-Streuung (%):',
        'fr': 'Variation aléatoire du cooldown (%) :',
        'pt': 'Variação aleatória do cooldown (%):',
    },
    'dialog.choose_sfx_title': {
        'sk': 'Zvukový súbor pre slot {n}',
        'en': 'Sound file for slot {n}',
        'ja': 'スロット {n} の音声ファイル',
        'zh': '插槽 {n} 的音效文件',
        'ru': 'Звуковой файл для слота {n}',
        'es': 'Archivo de sonido para el slot {n}',
        'de': 'Sounddatei für Slot {n}',
        'fr': 'Fichier son pour le slot {n}',
        'pt': 'Arquivo de som para o slot {n}',
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
    'dialog.jitter_note': {
        'sk': 'Rozptýlenie strieda cooldown náhodne v danom rozsahu,\naby pripomienky neprichádzali mechanicky pravidelne.',
        'en': "Jitter varies the cooldown randomly within this range, so reminders\ndon't arrive on a mechanically fixed beat.",
        'ja': 'ばらつきはクールダウンをこの範囲内でランダムに変化させ、\nリマインダーが機械的に一定のリズムで来ないようにします。',
        'zh': '浮动值会让冷却时间在此范围内随机变化，\n这样提醒就不会显得机械、按固定节拍出现。',
        'ru': 'Разброс случайно варьирует кулдаун в этом диапазоне,\nчтобы напоминания не звучали механически, по жёсткому ритму.',
        'es': 'La variación aleatoria hace que el cooldown fluctúe dentro de este rango,\npara que los recordatorios no lleguen con un ritmo mecánico y fijo.',
        'de': 'Die Streuung variiert den Cooldown zufällig innerhalb dieses Bereichs,\ndamit Erinnerungen nicht in einem mechanisch festen Takt kommen.',
        'fr': "La variation fait fluctuer le cooldown aléatoirement dans cette plage,\nafin que les rappels n'arrivent pas selon un rythme mécanique et fixe.",
        'pt': 'A variação faz o cooldown flutuar aleatoriamente dentro dessa faixa,\npara que os lembretes não cheguem num ritmo mecânico e fixo.',
    },
    'record.title': {
        'sk': 'Nahrávka pre slot {n}',
        'en': 'Recording for slot {n}',
        'ja': 'スロット {n} の録音',
        'zh': '插槽 {n} 的录音',
        'ru': 'Запись для слота {n}',
        'es': 'Grabación para el slot {n}',
        'de': 'Aufnahme für Slot {n}',
        'fr': 'Enregistrement pour le slot {n}',
        'pt': 'Gravação para o slot {n}',
    },
    'record.hint': {
        'sk': 'Nahraj si vlastnú hlásku alebo zvuk z mikrofónu.',
        'en': 'Record your own voice line or sound from the microphone.',
        'ja': 'マイクから自分の声や音を録音しましょう。',
        'zh': '通过麦克风录制你自己的语音条目或声音。',
        'ru': 'Запиши свою голосовую фразу или звук с микрофона.',
        'es': 'Graba tu propia frase de voz o sonido desde el micrófono.',
        'de': 'Nimm deine eigene Sprachzeile oder deinen Sound über das Mikrofon auf.',
        'fr': 'Enregistre ta propre réplique vocale ou ton propre son via le micro.',
        'pt': 'Grave sua própria fala de voz ou som pelo microfone.',
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
    'settings.title': {
        'sk': 'Globálne nastavenia',
        'en': 'Global settings',
        'ja': '全体設定',
        'zh': '全局设置',
        'ru': 'Глобальные настройки',
        'es': 'Configuración global',
        'de': 'Globale Einstellungen',
        'fr': 'Réglages globaux',
        'pt': 'Configurações globais',
    },
    'settings.cooldown': {
        'sk': 'Globálny cooldown:',
        'en': 'Global cooldown:',
        'ja': '全体クールダウン:',
        'zh': '全局冷却时间：',
        'ru': 'Глобальный кулдаун:',
        'es': 'Cooldown global:',
        'de': 'Globaler Cooldown:',
        'fr': 'Cooldown global :',
        'pt': 'Cooldown global:',
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
    'settings.overlap': {
        'sk': 'Hlásky môžu znieť cez seba',
        'en': 'Lines can overlap each other',
        'ja': 'セリフを重ねて再生する',
        'zh': '语音条目可以相互重叠播放',
        'ru': 'Фразы могут звучать одновременно',
        'es': 'Las frases pueden superponerse entre sí',
        'de': 'Zeilen können sich überlappen',
        'fr': 'Les répliques peuvent se chevaucher',
        'pt': 'As falas podem se sobrepor',
    },
    'settings.engine': {
        'sk': 'Motor TTS:',
        'en': 'TTS engine:',
        'ja': 'TTSエンジン:',
        'zh': '语音引擎：',
        'ru': 'Движок TTS:',
        'es': 'Motor TTS:',
        'de': 'TTS-Engine:',
        'fr': 'Moteur TTS :',
        'pt': 'Motor de TTS:',
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
        'sk': 'Edge Natural (prirodzený)',
        'en': 'Edge Natural (lifelike)',
        'ja': 'Edge Natural（自然な音声）',
        'zh': 'Edge Natural（自然逼真）',
        'ru': 'Edge Natural (естественный)',
        'es': 'Edge Natural (realista)',
        'de': 'Edge Natural (lebensecht)',
        'fr': 'Edge Natural (réaliste)',
        'pt': 'Edge Natural (realista)',
    },
    'engine.sapi': {
        'sk': 'Windows SAPI5 (offline)',
        'en': 'Windows SAPI5 (offline)',
        'ja': 'Windows SAPI5（オフライン）',
        'zh': 'Windows SAPI5（离线）',
        'ru': 'Windows SAPI5 (офлайн)',
        'es': 'Windows SAPI5 (sin conexión)',
        'de': 'Windows SAPI5 (offline)',
        'fr': 'Windows SAPI5 (hors ligne)',
        'pt': 'Windows SAPI5 (offline)',
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
    'status.stopped': {
        'sk': '●  Zastavené',
        'en': '●  Stopped',
        'ja': '●  停止中',
        'zh': '●  已停止',
        'ru': '●  Остановлено',
        'es': '●  Detenido',
        'de': '●  Gestoppt',
        'fr': '●  Arrêté',
        'pt': '●  Parado',
    },
    'status.running': {
        'sk': '●  Odpočúva sa (Aktívne)',
        'en': '●  Listening (Active)',
        'ja': '●  聴取中（アクティブ）',
        'zh': '●  监听中（运行中）',
        'ru': '●  Прослушивание (Активно)',
        'es': '●  Escuchando (Activo)',
        'de': '●  Hört zu (Aktiv)',
        'fr': "●  À l'écoute (Actif)",
        'pt': '●  Ouvindo (Ativo)',
    },
    'edge.ready': {
        'sk': '✓ hlásky pripravené',
        'en': '✓ voice lines ready',
        'ja': '✓ セリフの準備完了',
        'zh': '✓ 语音条目已就绪',
        'ru': '✓ голосовые фразы готовы',
        'es': '✓ frases de voz listas',
        'de': '✓ Sprachzeilen bereit',
        'fr': '✓ répliques vocales prêtes',
        'pt': '✓ falas de voz prontas',
    },
    'edge.generating': {
        'sk': '⟳ generujem hlásky...',
        'en': '⟳ generating voice lines...',
        'ja': '⟳ セリフを生成中...',
        'zh': '⟳ 正在生成语音条目…',
        'ru': '⟳ генерация голосовых фраз...',
        'es': '⟳ generando frases de voz...',
        'de': '⟳ Sprachzeilen werden generiert ...',
        'fr': '⟳ génération des répliques vocales...',
        'pt': '⟳ gerando falas de voz...',
    },
    'edge.partial': {
        'sk': '! iba {ok}/{total} hlások — skontroluj internet',
        'en': '! only {ok}/{total} lines - check your internet connection',
        'ja': '! {ok}/{total} 件のみ - インターネット接続を確認してください',
        'zh': '! 仅 {ok}/{total} 条完成 - 请检查你的网络连接',
        'ru': '! только {ok}/{total} фраз - проверь подключение к интернету',
        'es': '! solo {ok}/{total} frases - revisa tu conexión a internet',
        'de': '! nur {ok}/{total} Zeilen - prüfe deine Internetverbindung',
        'fr': '! seulement {ok}/{total} répliques - vérifie ta connexion internet',
        'pt': '! apenas {ok}/{total} falas - verifique sua conexão com a internet',
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
        'sk': 'edge-tts nie je nainštalované — hovorím starým SAPI5 hlasom.',
        'en': "edge-tts isn't installed - speaking with the old SAPI5 voice.",
        'ja': 'edge-tts がインストールされていません - 従来のSAPI5音声で話します。',
        'zh': '未安装 edge-tts - 正在使用旧版 SAPI5 语音朗读。',
        'ru': 'edge-tts не установлен - озвучка старым голосом SAPI5.',
        'es': 'edge-tts no está instalado - hablando con la antigua voz SAPI5.',
        'de': 'edge-tts ist nicht installiert - spreche mit der alten SAPI5-Stimme.',
        'fr': "edge-tts n'est pas installé - lecture avec l'ancienne voix SAPI5.",
        'pt': 'edge-tts não está instalado - falando com a voz antiga do SAPI5.',
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
        'sk': 'Slot odstránený ({label}).',
        'en': 'Slot removed ({label}).',
        'ja': 'スロットを削除しました（{label}）。',
        'zh': '插槽已删除（{label}）。',
        'ru': 'Слот удалён ({label}).',
        'es': 'Slot eliminado ({label}).',
        'de': 'Slot entfernt ({label}).',
        'fr': 'Slot supprimé ({label}).',
        'pt': 'Slot removido ({label}).',
    },
    'log.slot_only_one': {
        'sk': 'Musí zostať aspoň jeden slot.',
        'en': 'At least one slot must remain.',
        'ja': '少なくとも1つのスロットが必要です。',
        'zh': '至少需要保留一个插槽。',
        'ru': 'Должен остаться хотя бы один слот.',
        'es': 'Debe quedar al menos un slot.',
        'de': 'Mindestens ein Slot muss übrig bleiben.',
        'fr': 'Il doit rester au moins un slot.',
        'pt': 'Deve restar pelo menos um slot.',
    },
    'log.slot_sfx_set': {
        'sk': 'Slot {n}: zvuk = {name}',
        'en': 'Slot {n}: sound = {name}',
        'ja': 'スロット {n}: 音声 = {name}',
        'zh': '插槽 {n}：音效 = {name}',
        'ru': 'Слот {n}: звук = {name}',
        'es': 'Slot {n}: sonido = {name}',
        'de': 'Slot {n}: Sound = {name}',
        'fr': 'Slot {n} : son = {name}',
        'pt': 'Slot {n}: som = {name}',
    },
    'log.slot_recorded': {
        'sk': 'Slot {n}: nahrané do {name}',
        'en': 'Slot {n}: recorded to {name}',
        'ja': 'スロット {n}: {name} に録音しました',
        'zh': '插槽 {n}：已录制为 {name}',
        'ru': 'Слот {n}: записано в {name}',
        'es': 'Slot {n}: grabado en {name}',
        'de': 'Slot {n}: aufgenommen als {name}',
        'fr': 'Slot {n} : enregistré sous {name}',
        'pt': 'Slot {n}: gravado em {name}',
    },
    'log.slot_settings_saved': {
        'sk': 'Slot {n}: nastavenie uložené ({summary})',
        'en': 'Slot {n}: settings saved ({summary})',
        'ja': 'スロット {n}: 設定を保存しました（{summary}）',
        'zh': '插槽 {n}：设置已保存（{summary}）',
        'ru': 'Слот {n}: настройки сохранены ({summary})',
        'es': 'Slot {n}: configuración guardada ({summary})',
        'de': 'Slot {n}: Einstellungen gespeichert ({summary})',
        'fr': 'Slot {n} : réglages enregistrés ({summary})',
        'pt': 'Slot {n}: configurações salvas ({summary})',
    },
    'log.slot_key_bound': {
        'sk': 'Slot {n}: nový trigger = {key}',
        'en': 'Slot {n}: new trigger = {key}',
        'ja': 'スロット {n}: 新しいトリガー = {key}',
        'zh': '插槽 {n}：新触发器 = {key}',
        'ru': 'Слот {n}: новый триггер = {key}',
        'es': 'Slot {n}: nuevo disparador = {key}',
        'de': 'Slot {n}: neuer Trigger = {key}',
        'fr': 'Slot {n} : nouveau déclencheur = {key}',
        'pt': 'Slot {n}: novo gatilho = {key}',
    },
    'log.slot_sfx_missing': {
        'sk': 'Slot {n}: SFX súbor chýba ({name}).',
        'en': 'Slot {n}: SFX file is missing ({name}).',
        'ja': 'スロット {n}: SFXファイルが見つかりません（{name}）。',
        'zh': '插槽 {n}：音效文件缺失（{name}）。',
        'ru': 'Слот {n}: отсутствует файл SFX ({name}).',
        'es': 'Slot {n}: falta el archivo SFX ({name}).',
        'de': 'Slot {n}: SFX-Datei fehlt ({name}).',
        'fr': 'Slot {n} : fichier SFX manquant ({name}).',
        'pt': 'Slot {n}: arquivo SFX ausente ({name}).',
    },
    'log.slot_sfx_missing_fallback': {
        'sk': 'Slot {n}: SFX súbor chýba, hovorím text',
        'en': 'Slot {n}: SFX file is missing, speaking the text instead',
        'ja': 'スロット {n}: SFXファイルが見つからないため、代わりにテキストを読み上げます',
        'zh': '插槽 {n}：音效文件缺失，改为朗读文本',
        'ru': 'Слот {n}: отсутствует файл SFX, вместо этого озвучиваю текст',
        'es': 'Slot {n}: falta el archivo SFX, hablando el texto en su lugar',
        'de': 'Slot {n}: SFX-Datei fehlt, spreche stattdessen den Text',
        'fr': 'Slot {n} : fichier SFX manquant, lecture du texte à la place',
        'pt': 'Slot {n}: arquivo SFX ausente, falando o texto em vez disso',
    },
    'log.slot_sfx_missing_plain': {
        'sk': 'Slot {n}: SFX súbor chýba.',
        'en': 'Slot {n}: SFX file is missing.',
        'ja': 'スロット {n}: SFXファイルが見つかりません。',
        'zh': '插槽 {n}：音效文件缺失。',
        'ru': 'Слот {n}: отсутствует файл SFX.',
        'es': 'Slot {n}: falta el archivo SFX.',
        'de': 'Slot {n}: SFX-Datei fehlt.',
        'fr': 'Slot {n} : fichier SFX manquant.',
        'pt': 'Slot {n}: arquivo SFX ausente.',
    },
    'log.overlap_on': {
        'sk': 'Hlásky znejú cez seba.',
        'en': 'Lines now overlap each other.',
        'ja': 'セリフが重なって再生されるようになりました。',
        'zh': '语音条目现在会相互重叠播放。',
        'ru': 'Фразы теперь звучат одновременно.',
        'es': 'Las frases ahora se superponen entre sí.',
        'de': 'Zeilen überlappen sich jetzt.',
        'fr': 'Les répliques se chevauchent désormais.',
        'pt': 'As falas agora se sobrepõem.',
    },
    'log.overlap_off': {
        'sk': 'Hlásky sa prehrávajú za sebou.',
        'en': 'Lines now play one after another.',
        'ja': 'セリフが順番に再生されるようになりました。',
        'zh': '语音条目现在会依次播放。',
        'ru': 'Фразы теперь звучат по очереди.',
        'es': 'Las frases ahora se reproducen una tras otra.',
        'de': 'Zeilen spielen jetzt nacheinander ab.',
        'fr': "Les répliques jouent désormais l'une après l'autre.",
        'pt': 'As falas agora tocam uma após a outra.',
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
        'sk': 'Edge TTS: {n} hlások pripravených offline v cache.',
        'en': 'Edge TTS: {n} voice lines cached and ready offline.',
        'ja': 'Edge TTS: {n} 件のセリフをオフラインキャッシュに準備しました。',
        'zh': 'Edge TTS：{n} 条语音已缓存，可离线使用。',
        'ru': 'Edge TTS: {n} голосовых фраз закэшировано и готово к офлайн-использованию.',
        'es': 'Edge TTS: {n} frases de voz en caché y listas sin conexión.',
        'de': 'Edge TTS: {n} Sprachzeilen zwischengespeichert und offline bereit.',
        'fr': 'Edge TTS : {n} répliques vocales mises en cache et prêtes hors ligne.',
        'pt': 'Edge TTS: {n} falas de voz em cache e prontas offline.',
    },
    'log.edge_not_cached': {
        'sk': 'Edge hláska nie je v cache — hovorím cez SAPI5 a generujem na pozadí.',
        'en': "The Edge line isn't cached yet - speaking via SAPI5 while generating it in the background.",
        'ja': 'Edgeのセリフがまだキャッシュされていません - SAPI5で読み上げつつ、バックグラウンドで生成しています。',
        'zh': '该 Edge 语音条目尚未缓存 - 正在通过 SAPI5 朗读，同时在后台生成缓存。',
        'ru': 'Фраза Edge ещё не в кэше - озвучиваю через SAPI5, пока она генерируется в фоне.',
        'es': 'La frase de Edge aún no está en caché - hablando vía SAPI5 mientras se genera en segundo plano.',
        'de': 'Die Edge-Zeile ist noch nicht zwischengespeichert - spreche über SAPI5, während sie im Hintergrund generiert wird.',
        'fr': "La réplique Edge n'est pas encore en cache - lecture via SAPI5 pendant sa génération en arrière-plan.",
        'pt': 'A fala do Edge ainda não está em cache - falando via SAPI5 enquanto ela é gerada em segundo plano.',
    },
    'log.listening_on': {
        'sk': 'Odpočúvanie beží.',
        'en': 'Listening is running.',
        'ja': '聞き取りを実行中です。',
        'zh': '监听正在运行。',
        'ru': 'Прослушивание запущено.',
        'es': 'La escucha está activa.',
        'de': 'Zuhören läuft.',
        'fr': "L'écoute est active.",
        'pt': 'A escuta está ativa.',
    },
    'log.listening_off': {
        'sk': 'Odpočúvanie zastavené.',
        'en': 'Listening stopped.',
        'ja': '聞き取りを停止しました。',
        'zh': '监听已停止。',
        'ru': 'Прослушивание остановлено.',
        'es': 'Escucha detenida.',
        'de': 'Zuhören gestoppt.',
        'fr': 'Écoute arrêtée.',
        'pt': 'Escuta parada.',
    },
    'log.listener_error': {
        'sk': 'Listener sa nepodarilo spustiť: {err}',
        'en': "Couldn't start the listener: {err}",
        'ja': 'リスナーを開始できませんでした: {err}',
        'zh': '无法启动监听器：{err}',
        'ru': 'Не удалось запустить слушателя: {err}',
        'es': 'No se pudo iniciar el listener: {err}',
        'de': 'Listener konnte nicht gestartet werden: {err}',
        'fr': "Impossible de démarrer l'écouteur : {err}",
        'pt': 'Não foi possível iniciar o listener: {err}',
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
        'sk': 'Edge TTS: hlásku „{text}“ sa nepodarilo vygenerovať ({err})',
        'en': 'Edge TTS: couldn\'t generate the line "{text}" ({err})',
        'ja': 'Edge TTS: セリフ「{text}」の生成に失敗しました（{err}）',
        'zh': 'Edge TTS：无法生成语音「{text}」（{err}）',
        'ru': 'Edge TTS: не удалось сгенерировать фразу «{text}» ({err})',
        'es': 'Edge TTS: no se pudo generar la frase «{text}» ({err})',
        'de': 'Edge TTS: Zeile „{text}“ konnte nicht generiert werden ({err})',
        'fr': 'Edge TTS : impossible de générer la réplique « {text} » ({err})',
        'pt': 'Edge TTS: não foi possível gerar a fala "{text}" ({err})',
    },
    'log.sapi_ready': {
        'sk': 'TTS: SAPI5 pripravené ({n} hlasov)',
        'en': 'TTS: SAPI5 ready ({n} voices)',
        'ja': 'TTS: SAPI5 準備完了（{n} 件の音声）',
        'zh': '语音：SAPI5 已就绪（{n} 个语音）',
        'ru': 'TTS: SAPI5 готов ({n} голосов)',
        'es': 'TTS: SAPI5 listo ({n} voces)',
        'de': 'TTS: SAPI5 bereit ({n} Stimmen)',
        'fr': 'TTS : SAPI5 prêt ({n} voix)',
        'pt': 'TTS: SAPI5 pronto ({n} vozes)',
    },
    'log.sapi_unavailable': {
        'sk': 'TTS: SAPI5 nedostupné ({err}) — používam pyttsx3',
        'en': 'TTS: SAPI5 unavailable ({err}) - falling back to pyttsx3',
        'ja': 'TTS: SAPI5 が利用できません（{err}）- pyttsx3を使用します',
        'zh': '语音：SAPI5 不可用（{err}）- 回退到 pyttsx3',
        'ru': 'TTS: SAPI5 недоступен ({err}) - переход на pyttsx3',
        'es': 'TTS: SAPI5 no disponible ({err}) - usando pyttsx3 como alternativa',
        'de': 'TTS: SAPI5 nicht verfügbar ({err}) - Rückfall auf pyttsx3',
        'fr': 'TTS : SAPI5 indisponible ({err}) - repli sur pyttsx3',
        'pt': 'TTS: SAPI5 indisponível ({err}) - voltando para pyttsx3',
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
    'tray.toggle': {
        'sk': 'Štart / Stop',
        'en': 'Start / Stop',
        'ja': '開始 / 停止',
        'zh': '开始 / 停止',
        'ru': 'Старт / Стоп',
        'es': 'Iniciar / Detener',
        'de': 'Start / Stopp',
        'fr': 'Démarrer / Arrêter',
        'pt': 'Iniciar / Parar',
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
    'msgbox.edge_missing_title': {
        'sk': 'Zanshin',
        'en': 'Zanshin',
        'ja': 'Zanshin',
        'zh': 'Zanshin',
        'ru': 'Zanshin',
        'es': 'Zanshin',
        'de': 'Zanshin',
        'fr': 'Zanshin',
        'pt': 'Zanshin',
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
    'guide.panel_title': {
        'sk': '📖  Sprievodca / Čo je za tým',
        'en': '📖  Guide / What’s behind it',
        'ja': '📖  ガイド / その背景',
        'zh': '📖  指南 / 背后的道理',
        'ru': '📖  Справочник / Что за этим стоит',
        'es': '📖  Guía / Qué hay detrás',
        'de': '📖  Leitfaden / Was dahintersteckt',
        'fr': '📖  Guide / Ce qu’il y a derrière',
        'pt': '📖  Guia / O que há por trás',
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
        'sk': 'Inštrukcia pre hráča',
        'en': 'Instruction for the player',
        'ja': 'プレイヤーへの指示',
        'zh': '玩家操作说明',
        'ru': 'Инструкция для игрока',
        'es': 'Instrucción para el jugador',
        'de': 'Anleitung für den Spieler',
        'fr': 'Instruction pour le joueur',
        'pt': 'Instrução para o jogador',
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
        'sk': 'Ťažisko & panva',
        'en': 'Center of gravity & pelvis',
        'ja': '重心と骨盤',
        'zh': '重心与骨盆',
        'ru': 'Центр тяжести и таз',
        'es': 'Centro de gravedad y pelvis',
        'de': 'Schwerpunkt & Becken',
        'fr': 'Centre de gravité et bassin',
        'pt': 'Centro de gravidade e pelve',
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
    # 0.2: popis toho, co sa pri cviku deje s drzanim tela - nie tvrdenie
    # o "aktivacii stabilizacneho systemu" bez zdroja.
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
    # Poctivost (KNOWN_ISSUES.md bod 4): texty pod „Prečo to môže pomôcť“ uz
    # netvrdia mechanizmy ako fakt. Studia sa cituje len tam, kde je v
    # PHILOSOPHY_SOURCES (guide_content.py) a jej popisok to naozaj kryje;
    # inak text povie, ze ide o prax / tradiciu, a pozve hraca vyskusat to na
    # sebe („skús, či…“) - o hracoch nemame data, tak nehovorime „mnohým pomôže“.
    # Ostatne jazyky su z jazykovej fazy 0.2 (predtym docasne = en).
    # Strazi to tests/test_guide_honesty.py (vsetky jazyky).
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
        'sk': 'Keď sa appka ozve, nezosypeš sa dopredu – precíť, ako sa tvoje sedacie kosti zaboria do stoličky. Uvoľni spodnú časť brucha a nechaj ramená padnúť. Hlava hore, ťažisko dole.',
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
        'sk': 'Zuby & žuvacie svaly',
        'en': 'Jaw & chewing muscles',
        'ja': '歯と咀嚼筋',
        'zh': '下颌与咀嚼肌',
        'ru': 'Челюсть и жевательные мышцы',
        'es': 'Mandíbula y músculos masticatorios',
        'de': 'Kiefer & Kaumuskulatur',
        'fr': 'Mâchoire et muscles masticateurs',
        'pt': 'Mandíbula e músculos mastigatórios',
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
        'sk': 'Uvoľnenie & periféria',
        'en': 'Release & peripheral vision',
        'ja': '解放と周辺視野',
        'zh': '放松与周边视野',
        'ru': 'Отпускание и периферийное зрение',
        'es': 'Soltar y visión periférica',
        'de': 'Loslassen & peripheres Sehen',
        'fr': 'Relâche et vision périphérique',
        'pt': 'Soltura e visão periférica',
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
        'sk': 'Štýly dýchania a dychový reset',
        'en': 'Breathing styles and the breath reset',
        'ja': '呼吸法と呼吸リセット',
        'zh': '呼吸方式与呼吸重置',
        'ru': 'Стили дыхания и сброс дыхания',
        'es': 'Estilos de respiración y el reinicio de la respiración',
        'de': 'Atemstile und das Atem-Reset',
        'fr': 'Styles de respiration et réinitialisation du souffle',
        'pt': 'Estilos de respiração e o reset da respiração',
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
        'sk': 'Fyziologický vzdych (Cyclic Sighing — Dr. Andrew Huberman)',
        'en': 'Physiological sigh (Cyclic Sighing — Dr. Andrew Huberman)',
        'ja': '生理的ため息（サイクリック・サイイング — アンドリュー・ヒューバーマン博士）',
        'zh': '生理性叹息（周期性叹息法 — Andrew Huberman 博士）',
        'ru': 'Физиологический вздох (циклическое вздыхание — д-р Эндрю Хуберман)',
        'es': 'Suspiro fisiológico (Suspiro Cíclico — Dr. Andrew Huberman)',
        'de': 'Physiologisches Seufzen (Cyclic Sighing — Dr. Andrew Huberman)',
        'fr': 'Soupir physiologique (Cyclic Sighing — Dr Andrew Huberman)',
        'pt': 'Suspiro fisiológico (Suspiro Cíclico — Dr. Andrew Huberman)',
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
        'sk': 'Krabicové dýchanie (Box Breathing — tréning Navy SEALs)',
        'en': 'Box breathing (Navy SEAL training technique)',
        'ja': 'ボックス・ブリージング（ネイビーシールズのトレーニング法）',
        'zh': '方块呼吸法（海豹突击队训练技巧）',
        'ru': 'Квадратное дыхание (техника тренировки Navy SEAL)',
        'es': 'Respiración cuadrada (técnica de entrenamiento Navy SEAL)',
        'de': 'Box-Breathing (Navy-SEAL-Trainingstechnik)',
        'fr': "Respiration carrée (technique d'entraînement des Navy SEAL)",
        'pt': 'Respiração quadrada (técnica de treinamento dos Navy SEALs)',
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
        'sk': 'Stará budhistická metafora hovorí: keď prekročíš rieku na plti, nenosíš si ju ďalej na chrbte po súši — necháš ju na brehu. Táto appka je presne taká plť. Problém by nastal vtedy, ak by si bez nej vôbec nevedel uvoľniť telo, alebo keby si čakal, že softvér medituje za teba. V súlade to je vtedy, keď ju vnímaš ako tréningové kolieska: časom si telo možno začne na výdych a uvoľnenú čeľusť spomínať samo — a vtedy môžeš hlas aj zvuk nechať potichu ustúpiť do pozadia.',
        'en': 'An old Buddhist metaphor: once you’ve crossed the river on a raft, you don’t keep carrying it on your back down the road — you leave it on the bank. This app is exactly that raft. It would become a problem if you couldn’t relax your body at all without it running, or if you expected the software to meditate for you. It’s aligned when you treat it as training wheels: with time your body may start recalling the exhale and the loose jaw on its own — and then you can let the voice and sound quietly fade into the background.',
        'ja': '古い仏教のたとえがあります。筏で川を渡ったら、その筏を背負ったまま陸を歩き続けはしない — 岸に置いていく。このアプリはまさにその筏です。問題になるのは、これなしではまったく体をゆるめられなくなったとき、あるいはソフトウェアが代わりに瞑想してくれると期待したときです。うまく付き合えているのは、補助輪として使っているときです。やがて体が、長く吐く息やゆるんだ顎を自分から思い出すようになるかもしれません — そうしたら、音声も効果音も静かに背景へ退かせていいのです。',
        'zh': '一个古老的佛教比喻说：乘筏渡过河之后，你不会把木筏背在背上继续走陆路——你会把它留在岸边。这个应用正是这样一只木筏。如果没有它你就完全无法放松身体，或者你指望软件替你冥想，那就成了问题。当你把它当作学骑车时的辅助轮，才算用得其所：随着时间推移，身体也许会自己记起呼气和放松的下颌——那时你就可以让语音和音效悄悄退到幕后。',
        'ru': 'Старая буддийская метафора гласит: переправившись через реку на плоту, ты не несёшь его дальше по суше на спине — ты оставляешь его на берегу. Это приложение — именно такой плот. Проблема возникла бы, если бы ты вообще не мог расслабить тело без него или ждал, что программа будет медитировать за тебя. Всё на своём месте, когда ты воспринимаешь его как тренировочные колёсики: со временем тело, возможно, начнёт само вспоминать о выдохе и расслабленной челюсти — и тогда голос и звук можно тихо отпустить на задний план.',
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
        'sk': 'V japonskom kendžucu sa rozlišuje sacunintō — meč použitý len na drvenie súpera, dominanciu a ego — a kacuninken — meč, ktorým premáhaš vlastný strach a hnev. Ak niekto vezme uvoľnenie tela len ako „bio-hack na výhru“, skôr či neskôr narazí na strop: pri každej neférovej smrti nastúpi frustrácia, lebo hlava zostala toxická. Telo a emócie sú spojené nádoby — ťažko byť naozaj uvoľnený a zároveň plný slepej zlosti. Aj keď niekto začne z čisto sebeckého dôvodu (chcem vyhrávať), samotná prax ho môže nenápadne viesť k tomu, aby skrotil vlastné ego.',
        'en': 'In Japanese kenjutsu, a distinction is made between satsujinken - a sword used purely to crush an opponent, for dominance and ego - and katsujinken - a sword used to overcome your own fear and anger. If someone treats bodily release as a pure "win bio-hack," they\'ll sooner or later hit a ceiling: every unfair death still triggers frustration, because the mind stayed toxic. Body and emotion are connected vessels - it\'s hard to be truly relaxed and blindly furious at the same time. Even someone who starts for a purely selfish reason (I want to win) may find the practice itself quietly leading them to tame their own ego.',
        'ja': '日本の剣術では、殺人刀（せつにんとう）— 相手を打ち砕き、支配し、エゴを満たすためだけの剣 — と、活人剣（かつにんけん）— 自分の恐れや怒りに打ち勝つための剣 — が区別されます。体をゆるめることを「勝つためのバイオハック」としか見ないなら、遅かれ早かれ天井にぶつかります。理不尽なデスのたびに苛立ちが湧いてくる — 頭の中が毒されたままだからです。体と感情はつながった器です — 本当にゆるんでいながら、同時に盲目的な怒りに満ちているのは難しいものです。まったく利己的な理由（勝ちたい）から始めた人でも、実践そのものが、いつのまにか自分のエゴを手なずける方向へ導いてくれるかもしれません。',
        'zh': '日本剑术里区分两种剑：杀人刀（satsujintō）——只用来碾压对手、追求支配与小我的剑；以及活人剑（katsujinken）——用来战胜自己恐惧与愤怒的剑。如果有人只把放松身体当作“赢游戏的生物黑客技巧”，迟早会碰到天花板：每一次不公平的阵亡依然会引发挫败感，因为头脑仍是有毒的。身体和情绪是连通的容器——很难既真正放松，又满怀盲目的怒火。即使有人出于纯粹自私的理由开始（我想赢），练习本身也可能悄悄引导他驯服自己的小我。',
        'ru': 'В японском кэндзюцу различают сацунинто — меч, которым лишь сокрушают соперника ради доминирования и эго, — и кацунинкэн — меч, которым преодолевают собственный страх и гнев. Если кто-то воспринимает расслабление тела лишь как «био-хак для победы», рано или поздно он упрётся в потолок: при каждой нечестной смерти приходит фрустрация, потому что голова осталась токсичной. Тело и эмоции — сообщающиеся сосуды: трудно быть по-настоящему расслабленным и одновременно полным слепой злости. Даже если кто-то начинает из чисто эгоистичной причины (хочу побеждать), сама практика может незаметно привести его к тому, чтобы обуздать собственное эго.',
        'es': 'En el kenjutsu japonés se distingue entre el satsunintō — la espada usada solo para aplastar al rival, por dominio y ego — y el katsuninken — la espada con la que vences tu propio miedo y tu ira. Si alguien toma la relajación del cuerpo solo como un «biohack para ganar», tarde o temprano chocará con un techo: con cada muerte injusta llegará la frustración, porque la cabeza siguió tóxica. Cuerpo y emociones son vasos comunicantes — es difícil estar de verdad relajado y a la vez lleno de rabia ciega. Aunque alguien empiece por un motivo puramente egoísta (quiero ganar), la propia práctica puede llevarlo discretamente a domar su propio ego.',
        'de': 'Im japanischen Kenjutsu unterscheidet man Satsujintō — das Schwert, das nur dazu dient, den Gegner zu zermalmen, für Dominanz und Ego — und Katsujinken — das Schwert, mit dem du deine eigene Angst und Wut überwindest. Wer das Lockern des Körpers nur als „Bio-Hack zum Gewinnen“ nimmt, stößt früher oder später an eine Decke: Bei jedem unfairen Tod kommt Frust auf, weil der Kopf toxisch geblieben ist. Körper und Gefühle sind kommunizierende Röhren — es ist schwer, wirklich locker und zugleich voll blinder Wut zu sein. Auch wenn jemand aus einem rein egoistischen Grund anfängt (ich will gewinnen), kann ihn die Praxis selbst unauffällig dahin führen, das eigene Ego zu zähmen.',
        'fr': 'Dans le kenjutsu japonais, on distingue le satsujintō — l’épée qui ne sert qu’à écraser l’adversaire, pour la domination et l’ego — et le katsujinken — l’épée avec laquelle tu vaincs ta propre peur et ta colère. Si quelqu’un prend la détente du corps uniquement comme un « bio-hack pour gagner », il se heurtera tôt ou tard à un plafond : à chaque mort injuste, la frustration revient, parce que la tête est restée toxique. Le corps et les émotions sont des vases communicants — il est difficile d’être vraiment détendu et en même temps plein d’une colère aveugle. Même si quelqu’un commence pour une raison purement égoïste (je veux gagner), la pratique elle-même peut l’amener discrètement à apprivoiser son propre ego.',
        'pt': 'No kenjutsu japonês, há uma distinção entre o satsunintō — a espada usada só para esmagar o adversário, por dominância e ego — e o katsuninken — a espada com que você vence o próprio medo e a própria raiva. Se alguém toma o relaxamento do corpo só como um “bio-hack para vencer”, cedo ou tarde bate no teto: a cada morte injusta vem a frustração, porque a cabeça continuou tóxica. Corpo e emoções são vasos comunicantes — é difícil estar realmente relaxado e, ao mesmo tempo, cheio de raiva cega. Mesmo que alguém comece por um motivo puramente egoísta (quero ganhar), a própria prática pode, sem alarde, levá-lo a domar o próprio ego.',
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
        'sk': 'Zemitý dopad (Earth Thud)',
        'en': 'Earthy impact (Earth Thud)',
        'ja': '大地の衝撃音（アース・サッド）',
        'zh': '泥土般的撞击声（Earth Thud）',
        'ru': 'Земляной удар (Earth Thud)',
        'es': 'Impacto terroso (Earth Thud)',
        'de': 'Erdiger Aufprall (Earth Thud)',
        'fr': 'Impact terreux (Earth Thud)',
        'pt': 'Impacto terroso (Earth Thud)',
    },
    'sfx.zen.wood_temple_block': {
        'sk': 'Drevený blok kláštora (Temple Block)',
        'en': 'Temple wood block (Temple Block)',
        'ja': '寺院の木魚（テンプル・ブロック）',
        'zh': '寺院木鱼声（Temple Block）',
        'ru': 'Храмовый деревянный блок (Temple Block)',
        'es': 'Bloque de madera de templo (Temple Block)',
        'de': 'Holz-Tempelblock (Temple Block)',
        'fr': 'Bloc de bois de temple (Temple Block)',
        'pt': 'Bloco de madeira de templo (Temple Block)',
    },
    'sfx.zen.zen_singing_bowl': {
        'sk': 'Tibetská miska (Singing Bowl)',
        'en': 'Tibetan bowl (Singing Bowl)',
        'ja': 'チベタン・シンギングボウル',
        'zh': '西藏颂钵声（Singing Bowl）',
        'ru': 'Тибетская чаша (Singing Bowl)',
        'es': 'Cuenco tibetano (Singing Bowl)',
        'de': 'Tibetische Klangschale (Singing Bowl)',
        'fr': 'Bol tibétain (Singing Bowl)',
        'pt': 'Tigela tibetana (Singing Bowl)',
    },
    'sfx.zen.soft_breath_chime': {
        'sk': 'Jemný dych + cinknutie (Breath Chime)',
        'en': 'Soft breath + chime (Breath Chime)',
        'ja': 'やわらかな呼吸音+チャイム（ブレス・チャイム）',
        'zh': '轻柔呼吸声+风铃声（Breath Chime）',
        'ru': 'Мягкое дыхание + колокольчик (Breath Chime)',
        'es': 'Respiración suave + campanilla (Breath Chime)',
        'de': 'Sanfter Atem + Glockenspiel (Breath Chime)',
        'fr': 'Souffle doux + carillon (Breath Chime)',
        'pt': 'Respiração suave + sino (Breath Chime)',
    },
    'sfx.modern.mech_bass_thump': {
        'sk': 'Mechanický bass drop (Bass Thump)',
        'en': 'Mechanical bass drop (Bass Thump)',
        'ja': '機械的なベースドロップ（バス・サンプ）',
        'zh': '机械低音重击声（Bass Thump）',
        'ru': 'Механический бас-удар (Bass Thump)',
        'es': 'Golpe de bajo mecánico (Bass Thump)',
        'de': 'Mechanischer Bass-Schlag (Bass Thump)',
        'fr': 'Coup de basse mécanique (Bass Thump)',
        'pt': 'Batida de grave mecânica (Bass Thump)',
    },
    'sfx.modern.sfx_click_reload': {
        'sk': 'Magnetické cvaknutie (Click / Reload)',
        'en': 'Magnetic click (Click / Reload)',
        'ja': 'マグネティック・クリック音（クリック / リロード）',
        'zh': '磁吸咔哒声（Click / Reload）',
        'ru': 'Магнитный щелчок (Click / Reload)',
        'es': 'Clic magnético (Click / Reload)',
        'de': 'Magnetisches Klicken (Click / Reload)',
        'fr': 'Clic magnétique (Click / Reload)',
        'pt': 'Clique magnético (Click / Reload)',
    },
    'sfx.modern.sfx_lock_ping': {
        'sk': 'Laser-lock ping (UI Confirm)',
        'en': 'Laser-lock ping (UI Confirm)',
        'ja': 'レーザーロック・ピン音（UI確認音）',
        'zh': '激光锁定提示音（UI Confirm）',
        'ru': 'Пинг лазерного захвата (UI Confirm)',
        'es': 'Pitido de bloqueo láser (UI Confirm)',
        'de': 'Laser-Lock-Ping (UI Confirm)',
        'fr': 'Bip de verrouillage laser (UI Confirm)',
        'pt': 'Bipe de trava a laser (UI Confirm)',
    },
    'sfx.modern.vent_release': {
        'sk': 'Pretlakový ventil (Vent Release)',
        'en': 'Pressure vent (Vent Release)',
        'ja': '圧力弁（ベント・リリース）',
        'zh': '泄压排气声（Vent Release）',
        'ru': 'Сброс давления (Vent Release)',
        'es': 'Válvula de presión (Vent Release)',
        'de': 'Druckventil (Vent Release)',
        'fr': 'Soupape de pression (Vent Release)',
        'pt': 'Válvula de alívio de pressão (Vent Release)',
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
    'slot.default.grounding': {
        'sk': 'Grounded',
        'en': 'Grounded',
        'ja': '重心',
        'zh': '落地',
        'ru': 'Опора',
        'es': 'Con los pies en la tierra',
        'de': 'Geerdet',
        'fr': 'Ancré',
        'pt': 'Aterrado',
    },
    'slot.default.jaw': {
        'sk': 'Jaw',
        'en': 'Jaw',
        'ja': '顎',
        'zh': '牙关',
        'ru': 'Челюсть',
        'es': 'Mandíbula',
        'de': 'Kiefer',
        'fr': 'Mâchoire',
        'pt': 'Mandíbula',
    },
    'slot.default.release': {
        'sk': 'Release',
        'en': 'Release',
        'ja': '解放',
        'zh': '松开',
        'ru': 'Отпусти',
        'es': 'Suelta',
        'de': 'Loslassen',
        'fr': 'Relâche',
        'pt': 'Solta',
    },
    'slot.default.breath': {
        'sk': 'Breathe',
        'en': 'Breathe',
        'ja': '呼吸',
        'zh': '呼吸',
        'ru': 'Дыши',
        'es': 'Respira',
        'de': 'Atme',
        'fr': 'Respire',
        'pt': 'Respira',
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
    # cestina a bulharcina (0.2) - log „Jazyk rozhrania prepnuty na: …“ cita
    # `lang.{kod}` pre kazdy jazyk z LANGUAGES (cs/bg texty su v i18n_cs_bg.py)
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
# FAZA 3: in-game HUD, popisky vizualov a vyber monitora.
# sk/en su prelozene rucne; ostatne jazyky zatial dostavaju anglicku
# verziu (lepsie nez slovensky fallback) - na dopreklad rovnako ako
# zvysok suboru, viz poznamka v hlavicke modulu.
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
        'sk': 'Pri „Automaticky“ appka kreslí na tú obrazovku, na ktorej máš práve aktívne okno – takže na tú, kde hráš.',
        'en': 'With “Automatic” the app draws on whichever screen holds the active window - the one you are playing on.',
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
    # Najvyssie pasmo (tep nad hracovou vlastnou hranicou vysokeho tepu).
    # Zobrazovane meno je pokojne slovo bez zdravotneho ci poplasneho
    # nadychu ("Kriticka" znela ako diagnoza). Interny kluc ostava critical.
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
        'en': 'REMINDERS {n}',
        'ja': 'REMINDERS {n}',
        'zh': 'REMINDERS {n}',
        'ru': 'REMINDERS {n}',
        'es': 'REMINDERS {n}',
        'de': 'REMINDERS {n}',
        'fr': 'REMINDERS {n}',
        'pt': 'REMINDERS {n}',
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
        'sk': 'Vizuály a HUD sa budú kresliť na: {target}.',
        'en': 'Visuals and HUD will now draw on: {target}.',
        'ja': 'Visuals and HUD will now draw on: {target}.',
        'zh': 'Visuals and HUD will now draw on: {target}.',
        'ru': 'Visuals and HUD will now draw on: {target}.',
        'es': 'Visuals and HUD will now draw on: {target}.',
        'de': 'Visuals and HUD will now draw on: {target}.',
        'fr': 'Visuals and HUD will now draw on: {target}.',
        'pt': 'Visuals and HUD will now draw on: {target}.',
    },
    'log.exclusive_fullscreen': {
        'sk': 'Okno v popredí zaberá celú obrazovku. Ak je to hra a vizuály v nej nevidíš, beží asi v exkluzívnom fullscreene – Windows v ňom cudzie prekrytia nevykreslí. Prepni ju na „Bez okrajov / Borderless“.',
        'en': 'The window in front fills the whole screen. If it is a game and you cannot see the visuals, it is probably in exclusive fullscreen - Windows draws no overlay on top of that. Switch it to “Borderless”.',
        'ja': '前面のウィンドウが画面全体を占めています。それがゲームで、ビジュアルが見えないなら、おそらく排他的フルスクリーンで動いています – その上には、Windows はほかのオーバーレイを描画しません。「ボーダーレス / Borderless」に切り替えてください。',
        'zh': '前台窗口占满了整个屏幕。如果那是游戏，而你在里面看不到视觉效果，它大概是在独占全屏模式下运行——在这种模式下，Windows 不会绘制其他程序的叠加层。请把它切换到“无边框 / Borderless”。',
        'ru': 'Окно на переднем плане занимает весь экран. Если это игра и визуалов в ней не видно, она, вероятно, работает в эксклюзивном полноэкранном режиме – Windows не рисует поверх него чужие оверлеи. Переключи её в «Без рамки / Borderless».',
        'es': 'La ventana en primer plano ocupa toda la pantalla. Si es un juego y no ves los visuales en él, probablemente esté en pantalla completa exclusiva – ahí Windows no dibuja superposiciones ajenas. Cámbialo a «Sin bordes / Borderless».',
        'de': 'Das Fenster im Vordergrund füllt den ganzen Bildschirm. Wenn es ein Spiel ist und du die Visuals darin nicht siehst, läuft es vermutlich im exklusiven Vollbild – darin zeichnet Windows keine fremden Overlays. Stell es auf „Randlos / Borderless“ um.',
        'fr': 'La fenêtre au premier plan occupe tout l’écran. Si c’est un jeu et que tu n’y vois pas les visuels, il tourne sans doute en plein écran exclusif – Windows n’y dessine pas les superpositions externes. Passe-le en « Sans bordure / Borderless ».',
        'pt': 'A janela em primeiro plano ocupa a tela inteira. Se for um jogo e você não vê os visuais nele, provavelmente está em tela cheia exclusiva – nesse modo o Windows não desenha sobreposições de outros programas. Mude o jogo para “Sem bordas / Borderless”.',
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
})

# --------------------------------------------------------------------------
# REDIZAJN: stranky Dnes / Spustace / V hre, dychajuci pas, nova struktura
# Nastaveni. sk/en rucne, ostatne jazyky zatial anglicky - na dopreklad.
# --------------------------------------------------------------------------

STRINGS.update({
    'app.version_short': {
        # drz v sulade s MyAppVersion v Dandurf.iss (instalator)
        #
        # "alfa 0.2", nie "2.1": cislovanie 2.x bolo z casov, ked appka
        # mierila na Steam ako pokracovanie predchodcu. Na GitHub ide ako
        # to, cim naozaj je - prva verejna alfa.
        'sk': 'alfa 0.2.1',
        'en': 'alpha 0.2.1',
        'ja': 'alpha 0.2.1',
        'zh': 'alpha 0.2.1',
        'ru': 'alpha 0.2.1',
        'es': 'alpha 0.2.1',
        'de': 'alpha 0.2.1',
        'fr': 'alpha 0.2.1',
        'pt': 'alpha 0.2.1',
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
        'sk': 'Spúšťače',
        'en': 'Triggers',
        'ja': 'Triggers',
        'zh': 'Triggers',
        'ru': 'Triggers',
        'es': 'Triggers',
        'de': 'Triggers',
        'fr': 'Triggers',
        'pt': 'Triggers',
    },
    # Uz to nie je len "v hre": senzor tepu sa presunul na tuto stranku
    # hore. Bez hodiniek nema widget co kreslit, takze patria k sebe.
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
    'kamae.bar_title': {
        'sk': 'Hlavný vypínač',
        'en': 'Main switch',
        'ja': 'メインスイッチ',
        'zh': '主开关',
        'ru': 'Главный выключатель',
        'es': 'Interruptor principal',
        'de': 'Hauptschalter',
        'fr': 'Interrupteur principal',
        'pt': 'Interruptor principal',
    },
    'kamae.bar_sub': {
        'sk': 'Klikni ▶ vľavo. Keď počúvam, pás dýcha — inak stojí.',
        'en': "Click ▶ on the left. When I'm listening the bar breathes; otherwise it rests.",
        'ja': '左の▶をクリック。聞いている間はバーが呼吸し、そうでなければ止まります。',
        'zh': '点击左侧 ▶。我在聆听时呼吸条会起伏，否则静止。',
        'ru': 'Нажми ▶ слева. Когда слушаю — полоса дышит, иначе стоит.',
        'es': 'Pulsa ▶ a la izquierda. Cuando escucho, la barra respira; si no, se detiene.',
        'de': 'Klick ▶ links. Wenn ich höre, atmet die Leiste; sonst ruht sie.',
        'fr': "Clique sur ▶ à gauche. Quand j'écoute, la barre respire ; sinon elle s'arrête.",
        'pt': 'Clique em ▶ à esquerda. Quando estou ouvindo, a barra respira; senão, fica parada.',
    },
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
        'sk': "Väčšinu posledných večerov pri hre sa ti tep držal blízko tvojho pokoja. Skús ďalší zápas beze mňa. Ak som ti bola plťou cez rieku, na druhom brehu ma netreba niesť ďalej — kráčaj po svojich. A keby si ma niekedy potreboval, breh je vždy tu.",
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
        'sk': 'Počúvam',
        'en': 'Listening',
        'ja': 'Listening',
        'zh': 'Listening',
        'ru': 'Listening',
        'es': 'Listening',
        'de': 'Listening',
        'fr': 'Listening',
        'pt': 'Listening',
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
    'sidebar.state_tip': {
        'sk': 'Zelená — appka počúva. Červená — nepočúva. Spustíš ju v páse na stránke Dnes.',
        'en': 'Green — the app is listening. Red — it is not. Start it in the bar on the Today page.',
        'ja': 'Green — the app is listening. Red — it is not. Start it in the bar on the Today page.',
        'zh': 'Green — the app is listening. Red — it is not. Start it in the bar on the Today page.',
        'ru': 'Green — the app is listening. Red — it is not. Start it in the bar on the Today page.',
        'es': 'Green — the app is listening. Red — it is not. Start it in the bar on the Today page.',
        'de': 'Green — the app is listening. Red — it is not. Start it in the bar on the Today page.',
        'fr': 'Green — the app is listening. Red — it is not. Start it in the bar on the Today page.',
        'pt': 'Green — the app is listening. Red — it is not. Start it in the bar on the Today page.',
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
    # DVE ZNENIA, nie jedno. Appka sa vie spustit sama pri starte hry, ale
    # len ked je zapnute automaticke prepinanie profilov - inak by veta
    # slubovala nieco, co sa nestane.
    # --- sekcia "O appke" (Nastavenia -> Vseobecne, hned pod Datami) ---
    # Je to OSOBNY text autora, nie popis funkcie. Preto je aj v anglictine
    # v jeho vlastnom zneni a neprekladá sa do dalsich jazykov - prelozeny
    # osobny text uz nie je ten isty text.
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
        'sk': 'Ahojte, tu Dandurfin.',
        'en': 'Hey everyone, Dandurfin here.',
        'ja': 'Hey everyone, Dandurfin here.',
        'zh': 'Hey everyone, Dandurfin here.',
        'ru': 'Hey everyone, Dandurfin here.',
        'es': 'Hey everyone, Dandurfin here.',
        'de': 'Hey everyone, Dandurfin here.',
        'fr': 'Hey everyone, Dandurfin here.',
        'pt': 'Hey everyone, Dandurfin here.',
    },
    'about.body': {
        'sk': 'Prečo vlastne Zanshin vznikol? Ako človek, ktorý trávi pri počítači veľkú časť dňa — streamujem a hrám — som si časom všimol vzorec. Pri hraní často skĺzneme do úplného „autopilota“. Buď sa zaberieme tak, že stratíme pojem o čase aj o vlastnom tele, alebo naopak chytíme zbytočný tilt a naštveme sa, keď sa nedarí.\n\nHľadal som spôsob, ako si udržať chladnú hlavu a ostať vo „flow“ aj uprostred akcie alebo v sweaty ranked zápasoch. Vtedy som narazil na pojem zanshin — v bojových umeniach označuje stav plného sústredenia, uvoľnenia a čistej hlavy pripravenej na čokoľvek.\n\nTúto appku som napísal z obyčajnej osobnej potreby. Chcel som nenápadného pomocníka na pozadí, ktorý ma nenechá vyhorieť, občas mi pripomenie zhlboka sa nadýchnuť a udrží ma pri zemi. Nie sú to žiadne komplikované ezoterické cvičenia — ide jednoducho o to, aby nás hry viac bavili, aby sme hrali lepšie a hlavne aby sme sa nenaštvali pre nič za nič.\n\nVyrástol som s hrami ako mnohí z mojej generácie. Za očami sa v nás deje viac, než vidno. Zanshin je môj pokus skúsiť to v mieri: niečo, čo si všimne, nič nechce a nič nepredáva.\n\nA teraz narovinu: nie som programátor ani grafik. Túto appku som napísal vibe codingom — teda spolu s AI, vetu po vete, a učil som sa za pochodu. To, čo som priniesol ja, je nápad a roky strávené pri počítači.\n\nStojím na pleciach obrov. Nič z toho, čo appka robí, som nevymyslel — dýchanie, sústredenie, uvoľnená čeľusť, výskum o tepe a strese aj nástroje, v ktorých je to napísané. Všetko to niekto spravil predo mnou a nechal to voľne dostupné. Preto je Zanshin zadarmo a otvorený pod licenciou GPLv3: ktokoľvek si môže kód pozrieť, upraviť ho a posunúť ďalej — len ho nesmie zavrieť. Kto ho posunie ďalej, musí s ním odovzdať aj zdrojový kód a tú istú licenciu. Zdedil som to takto a chcem to takto aj odovzdať.\n\nAk ti toto nastavenie sedí, alebo si len chceš zahrať a pokecať, zastav sa u nás:',
        'en': 'Why did Zanshin actually come to be? As someone who spends a huge chunk of the day at the PC, streaming and playing games, I noticed a pattern over time. We often slip into complete “autopilot” mode while gaming. We either get so absorbed that we completely lose track of time and our own bodies, or on the flip side, we catch unnecessary tilt and get frustrated when things go wrong.\n\nI was looking for a way to keep a cool head and stay in the “flow” even in the middle of intense action or sweaty ranked matches. That is when I came across the concept of zanshin — which in martial arts refers to a state of being fully focused, relaxed, and having a clear mind ready for anything.\n\nI coded this app out of a simple personal need. I wanted a subtle background helper that prevents me from burning out, reminds me to take a deep breath every now and then, and keeps me grounded. It is not about any complicated esoteric exercises; it is simply about enjoying our games more, performing better, and most importantly, not getting tilted over nothing.\n\nI grew up with games, like a lot of my generation. More goes on behind the eyes than anyone sees. Zanshin is my attempt to try it in peace: something that notices, wants nothing and sells nothing.\n\nAnd straight up: I am not a programmer or an artist. I vibe coded this app — together with AI, line by line, learning as I went. What I brought to it is the idea and years spent at the PC.\n\nI am standing on the shoulders of giants. Nothing this app does was invented by me — the breathing, the focus, the unclenched jaw, the research on heart rate and stress, the tools it is written in. Someone did all of it before me and left it out in the open. That is why Zanshin is free and open under the GPLv3 licence: anyone can read the code, change it and pass it on — they just cannot close it up. Whoever passes it on has to hand over the source and the same licence with it. I inherited it this way and I want to hand it on the same way.\n\nIf you vibe with this mindset, or if you just want to play some games and hang out, definitely drop by our community:',
        'ja': 'Why did Zanshin actually come to be? As someone who spends a huge chunk of the day at the PC, streaming and playing games, I noticed a pattern over time. We often slip into complete “autopilot” mode while gaming. We either get so absorbed that we completely lose track of time and our own bodies, or on the flip side, we catch unnecessary tilt and get frustrated when things go wrong.\n\nI was looking for a way to keep a cool head and stay in the “flow” even in the middle of intense action or sweaty ranked matches. That is when I came across the concept of zanshin — which in martial arts refers to a state of being fully focused, relaxed, and having a clear mind ready for anything.\n\nI coded this app out of a simple personal need. I wanted a subtle background helper that prevents me from burning out, reminds me to take a deep breath every now and then, and keeps me grounded. It is not about any complicated esoteric exercises; it is simply about enjoying our games more, performing better, and most importantly, not getting tilted over nothing.\n\nI grew up with games, like a lot of my generation. More goes on behind the eyes than anyone sees. Zanshin is my attempt to try it in peace: something that notices, wants nothing and sells nothing.\n\nAnd straight up: I am not a programmer or an artist. I vibe coded this app — together with AI, line by line, learning as I went. What I brought to it is the idea and years spent at the PC.\n\nI am standing on the shoulders of giants. Nothing this app does was invented by me — the breathing, the focus, the unclenched jaw, the research on heart rate and stress, the tools it is written in. Someone did all of it before me and left it out in the open. That is why Zanshin is free and open under the GPLv3 licence: anyone can read the code, change it and pass it on — they just cannot close it up. Whoever passes it on has to hand over the source and the same licence with it. I inherited it this way and I want to hand it on the same way.\n\nIf you vibe with this mindset, or if you just want to play some games and hang out, definitely drop by our community:',
        'zh': 'Why did Zanshin actually come to be? As someone who spends a huge chunk of the day at the PC, streaming and playing games, I noticed a pattern over time. We often slip into complete “autopilot” mode while gaming. We either get so absorbed that we completely lose track of time and our own bodies, or on the flip side, we catch unnecessary tilt and get frustrated when things go wrong.\n\nI was looking for a way to keep a cool head and stay in the “flow” even in the middle of intense action or sweaty ranked matches. That is when I came across the concept of zanshin — which in martial arts refers to a state of being fully focused, relaxed, and having a clear mind ready for anything.\n\nI coded this app out of a simple personal need. I wanted a subtle background helper that prevents me from burning out, reminds me to take a deep breath every now and then, and keeps me grounded. It is not about any complicated esoteric exercises; it is simply about enjoying our games more, performing better, and most importantly, not getting tilted over nothing.\n\nI grew up with games, like a lot of my generation. More goes on behind the eyes than anyone sees. Zanshin is my attempt to try it in peace: something that notices, wants nothing and sells nothing.\n\nAnd straight up: I am not a programmer or an artist. I vibe coded this app — together with AI, line by line, learning as I went. What I brought to it is the idea and years spent at the PC.\n\nI am standing on the shoulders of giants. Nothing this app does was invented by me — the breathing, the focus, the unclenched jaw, the research on heart rate and stress, the tools it is written in. Someone did all of it before me and left it out in the open. That is why Zanshin is free and open under the GPLv3 licence: anyone can read the code, change it and pass it on — they just cannot close it up. Whoever passes it on has to hand over the source and the same licence with it. I inherited it this way and I want to hand it on the same way.\n\nIf you vibe with this mindset, or if you just want to play some games and hang out, definitely drop by our community:',
        'ru': 'Why did Zanshin actually come to be? As someone who spends a huge chunk of the day at the PC, streaming and playing games, I noticed a pattern over time. We often slip into complete “autopilot” mode while gaming. We either get so absorbed that we completely lose track of time and our own bodies, or on the flip side, we catch unnecessary tilt and get frustrated when things go wrong.\n\nI was looking for a way to keep a cool head and stay in the “flow” even in the middle of intense action or sweaty ranked matches. That is when I came across the concept of zanshin — which in martial arts refers to a state of being fully focused, relaxed, and having a clear mind ready for anything.\n\nI coded this app out of a simple personal need. I wanted a subtle background helper that prevents me from burning out, reminds me to take a deep breath every now and then, and keeps me grounded. It is not about any complicated esoteric exercises; it is simply about enjoying our games more, performing better, and most importantly, not getting tilted over nothing.\n\nI grew up with games, like a lot of my generation. More goes on behind the eyes than anyone sees. Zanshin is my attempt to try it in peace: something that notices, wants nothing and sells nothing.\n\nAnd straight up: I am not a programmer or an artist. I vibe coded this app — together with AI, line by line, learning as I went. What I brought to it is the idea and years spent at the PC.\n\nI am standing on the shoulders of giants. Nothing this app does was invented by me — the breathing, the focus, the unclenched jaw, the research on heart rate and stress, the tools it is written in. Someone did all of it before me and left it out in the open. That is why Zanshin is free and open under the GPLv3 licence: anyone can read the code, change it and pass it on — they just cannot close it up. Whoever passes it on has to hand over the source and the same licence with it. I inherited it this way and I want to hand it on the same way.\n\nIf you vibe with this mindset, or if you just want to play some games and hang out, definitely drop by our community:',
        'es': 'Why did Zanshin actually come to be? As someone who spends a huge chunk of the day at the PC, streaming and playing games, I noticed a pattern over time. We often slip into complete “autopilot” mode while gaming. We either get so absorbed that we completely lose track of time and our own bodies, or on the flip side, we catch unnecessary tilt and get frustrated when things go wrong.\n\nI was looking for a way to keep a cool head and stay in the “flow” even in the middle of intense action or sweaty ranked matches. That is when I came across the concept of zanshin — which in martial arts refers to a state of being fully focused, relaxed, and having a clear mind ready for anything.\n\nI coded this app out of a simple personal need. I wanted a subtle background helper that prevents me from burning out, reminds me to take a deep breath every now and then, and keeps me grounded. It is not about any complicated esoteric exercises; it is simply about enjoying our games more, performing better, and most importantly, not getting tilted over nothing.\n\nI grew up with games, like a lot of my generation. More goes on behind the eyes than anyone sees. Zanshin is my attempt to try it in peace: something that notices, wants nothing and sells nothing.\n\nAnd straight up: I am not a programmer or an artist. I vibe coded this app — together with AI, line by line, learning as I went. What I brought to it is the idea and years spent at the PC.\n\nI am standing on the shoulders of giants. Nothing this app does was invented by me — the breathing, the focus, the unclenched jaw, the research on heart rate and stress, the tools it is written in. Someone did all of it before me and left it out in the open. That is why Zanshin is free and open under the GPLv3 licence: anyone can read the code, change it and pass it on — they just cannot close it up. Whoever passes it on has to hand over the source and the same licence with it. I inherited it this way and I want to hand it on the same way.\n\nIf you vibe with this mindset, or if you just want to play some games and hang out, definitely drop by our community:',
        'de': 'Why did Zanshin actually come to be? As someone who spends a huge chunk of the day at the PC, streaming and playing games, I noticed a pattern over time. We often slip into complete “autopilot” mode while gaming. We either get so absorbed that we completely lose track of time and our own bodies, or on the flip side, we catch unnecessary tilt and get frustrated when things go wrong.\n\nI was looking for a way to keep a cool head and stay in the “flow” even in the middle of intense action or sweaty ranked matches. That is when I came across the concept of zanshin — which in martial arts refers to a state of being fully focused, relaxed, and having a clear mind ready for anything.\n\nI coded this app out of a simple personal need. I wanted a subtle background helper that prevents me from burning out, reminds me to take a deep breath every now and then, and keeps me grounded. It is not about any complicated esoteric exercises; it is simply about enjoying our games more, performing better, and most importantly, not getting tilted over nothing.\n\nI grew up with games, like a lot of my generation. More goes on behind the eyes than anyone sees. Zanshin is my attempt to try it in peace: something that notices, wants nothing and sells nothing.\n\nAnd straight up: I am not a programmer or an artist. I vibe coded this app — together with AI, line by line, learning as I went. What I brought to it is the idea and years spent at the PC.\n\nI am standing on the shoulders of giants. Nothing this app does was invented by me — the breathing, the focus, the unclenched jaw, the research on heart rate and stress, the tools it is written in. Someone did all of it before me and left it out in the open. That is why Zanshin is free and open under the GPLv3 licence: anyone can read the code, change it and pass it on — they just cannot close it up. Whoever passes it on has to hand over the source and the same licence with it. I inherited it this way and I want to hand it on the same way.\n\nIf you vibe with this mindset, or if you just want to play some games and hang out, definitely drop by our community:',
        'fr': 'Why did Zanshin actually come to be? As someone who spends a huge chunk of the day at the PC, streaming and playing games, I noticed a pattern over time. We often slip into complete “autopilot” mode while gaming. We either get so absorbed that we completely lose track of time and our own bodies, or on the flip side, we catch unnecessary tilt and get frustrated when things go wrong.\n\nI was looking for a way to keep a cool head and stay in the “flow” even in the middle of intense action or sweaty ranked matches. That is when I came across the concept of zanshin — which in martial arts refers to a state of being fully focused, relaxed, and having a clear mind ready for anything.\n\nI coded this app out of a simple personal need. I wanted a subtle background helper that prevents me from burning out, reminds me to take a deep breath every now and then, and keeps me grounded. It is not about any complicated esoteric exercises; it is simply about enjoying our games more, performing better, and most importantly, not getting tilted over nothing.\n\nI grew up with games, like a lot of my generation. More goes on behind the eyes than anyone sees. Zanshin is my attempt to try it in peace: something that notices, wants nothing and sells nothing.\n\nAnd straight up: I am not a programmer or an artist. I vibe coded this app — together with AI, line by line, learning as I went. What I brought to it is the idea and years spent at the PC.\n\nI am standing on the shoulders of giants. Nothing this app does was invented by me — the breathing, the focus, the unclenched jaw, the research on heart rate and stress, the tools it is written in. Someone did all of it before me and left it out in the open. That is why Zanshin is free and open under the GPLv3 licence: anyone can read the code, change it and pass it on — they just cannot close it up. Whoever passes it on has to hand over the source and the same licence with it. I inherited it this way and I want to hand it on the same way.\n\nIf you vibe with this mindset, or if you just want to play some games and hang out, definitely drop by our community:',
        'pt': 'Why did Zanshin actually come to be? As someone who spends a huge chunk of the day at the PC, streaming and playing games, I noticed a pattern over time. We often slip into complete “autopilot” mode while gaming. We either get so absorbed that we completely lose track of time and our own bodies, or on the flip side, we catch unnecessary tilt and get frustrated when things go wrong.\n\nI was looking for a way to keep a cool head and stay in the “flow” even in the middle of intense action or sweaty ranked matches. That is when I came across the concept of zanshin — which in martial arts refers to a state of being fully focused, relaxed, and having a clear mind ready for anything.\n\nI coded this app out of a simple personal need. I wanted a subtle background helper that prevents me from burning out, reminds me to take a deep breath every now and then, and keeps me grounded. It is not about any complicated esoteric exercises; it is simply about enjoying our games more, performing better, and most importantly, not getting tilted over nothing.\n\nI grew up with games, like a lot of my generation. More goes on behind the eyes than anyone sees. Zanshin is my attempt to try it in peace: something that notices, wants nothing and sells nothing.\n\nAnd straight up: I am not a programmer or an artist. I vibe coded this app — together with AI, line by line, learning as I went. What I brought to it is the idea and years spent at the PC.\n\nI am standing on the shoulders of giants. Nothing this app does was invented by me — the breathing, the focus, the unclenched jaw, the research on heart rate and stress, the tools it is written in. Someone did all of it before me and left it out in the open. That is why Zanshin is free and open under the GPLv3 licence: anyone can read the code, change it and pass it on — they just cannot close it up. Whoever passes it on has to hand over the source and the same licence with it. I inherited it this way and I want to hand it on the same way.\n\nIf you vibe with this mindset, or if you just want to play some games and hang out, definitely drop by our community:',
    },
    'about.between_lines': {
        'sk': 'Pre toho, kto číta medzi riadkami:\n\nTáto appka nemeria stres. Meria medzeru — medzi tým, čo hovorí tvoj tep, a tým, čo naozaj cítiš. Číslo je povrch; ty si hĺbka.\n\nA keď sa naučíš počúvať tú medzeru v sebe, začneš ju počuť aj inde — v tom, čo ľudia píšu a čo myslia, čo si žiadajú a čo potrebujú.\n\nNič sa nestráca. Len sa to premieňa — aj pozornosť. Drž dlaň otvorenú.',
        'en': 'For the one who reads between the lines:\n\nThis app does not measure stress. It measures the gap — between what your heart rate says and what you truly feel. The number is the surface; you are the depth.\n\nAnd once you learn to hear that gap in yourself, you will start to hear it elsewhere too — in what people write and what they mean, in what they ask for and what they need.\n\nNothing is lost. It only transforms — attention too. Keep your palm open.',
    },
    # 0.2: zdrojak v instalatore nie je (len skompilovany build) - veta
    # "ide s nim aj zdrojovy kod" preto neplatila. Oficialny zdroj a
    # oznacenie upravenych verzii podla LICENSE-DESIGN.md (GPLv3 7c/7e).
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
    'about.links': {
        'sk': 'Nájdeš ma tu',
        'en': 'Find me here',
        'ja': 'Find me here',
        'zh': 'Find me here',
        'ru': 'Find me here',
        'es': 'Find me here',
        'de': 'Find me here',
        'fr': 'Find me here',
        'pt': 'Find me here',
    },
    'kamae.stopped_sub_auto': {
        'sk': 'Nesledujem nič. Spustíš ma tlačidlom vľavo, alebo sa spustím sama, keď zapneš {games}.',
        'en': 'Not watching anything. Start me with the button on the left, or I start by myself when you launch {games}.',
        'ja': '何も見ていません。左のボタンで開始できます。{games} を起動すれば、自分で開始します。',
        'zh': '什么都没在看。用左边的按钮启动我，或者当你打开 {games} 时，我会自己启动。',
        'ru': 'Ничего не отслеживаю. Запусти меня кнопкой слева — или я запущусь сама, когда ты включишь {games}.',
        'es': 'No vigilo nada. Iníciame con el botón de la izquierda, o me pongo en marcha yo sola cuando inicies {games}.',
        'de': 'Ich beobachte nichts. Starte mich mit dem Knopf links, oder ich starte selbst, sobald du {games} öffnest.',
        'fr': 'Je ne surveille rien. Démarre-moi avec le bouton à gauche, ou je démarre toute seule quand tu lances {games}.',
        'pt': 'Não estou acompanhando nada. Você me inicia com o botão à esquerda, ou eu começo sozinha quando você abrir {games}.',
    },
    'kamae.stopped_sub': {
        'sk': 'Nesledujem nič. Spustíš ma tlačidlom vľavo.',
        'en': 'Not watching anything. Start me with the button on the left.',
        'ja': 'Not watching anything. Start me with the button on the left.',
        'zh': 'Not watching anything. Start me with the button on the left.',
        'ru': 'Not watching anything. Start me with the button on the left.',
        'es': 'Not watching anything. Start me with the button on the left.',
        'de': 'Not watching anything. Start me with the button on the left.',
        'fr': 'Not watching anything. Start me with the button on the left.',
        'pt': 'Not watching anything. Start me with the button on the left.',
    },
    # POZN: tu boli 'kamae.meta_time', 'kamae.meta_triggers' a
    # 'kamae.meta_bpm' - popisky troch cisel vpravo v dychajucom pase.
    # Cisla z pasu odisli (viz `ui_kit.KamaeBar`), takze kluce uz nemal co
    # citat a boli by to len tri dalsie retazce na prekladanie do vsetkych
    # jazykov.
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
    'dnes.hr_connected': {
        'sk': 'hodinky pripojené',
        'en': 'watch connected',
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
    'dnes.load_note': {
        'sk': 'Počítané z tepu voči tvojej vlastnej pokojovej základni. Nie je to HRV — hodinky posielajú len tep, nie rozostupy medzi údermi.',
        'en': 'Derived from heart rate against your own resting baseline. This is not HRV - the watch sends beats per minute, not the gaps between beats.',
        'ja': 'Derived from heart rate against your own resting baseline. This is not HRV - the watch sends beats per minute, not the gaps between beats.',
        'zh': 'Derived from heart rate against your own resting baseline. This is not HRV - the watch sends beats per minute, not the gaps between beats.',
        'ru': 'Derived from heart rate against your own resting baseline. This is not HRV - the watch sends beats per minute, not the gaps between beats.',
        'es': 'Derived from heart rate against your own resting baseline. This is not HRV - the watch sends beats per minute, not the gaps between beats.',
        'de': 'Derived from heart rate against your own resting baseline. This is not HRV - the watch sends beats per minute, not the gaps between beats.',
        'fr': 'Derived from heart rate against your own resting baseline. This is not HRV - the watch sends beats per minute, not the gaps between beats.',
        'pt': 'Derived from heart rate against your own resting baseline. This is not HRV - the watch sends beats per minute, not the gaps between beats.',
    },
    'dnes.session_title': {
        'sk': 'Táto relácia',
        'en': 'This session',
        'ja': 'This session',
        'zh': 'This session',
        'ru': 'This session',
        'es': 'This session',
        'de': 'This session',
        'fr': 'This session',
        'pt': 'This session',
    },
    'dnes.stat_min': {
        'sk': 'Najnižší tep',
        'en': 'Lowest',
        'ja': 'Lowest',
        'zh': 'Lowest',
        'ru': 'Lowest',
        'es': 'Lowest',
        'de': 'Lowest',
        'fr': 'Lowest',
        'pt': 'Lowest',
    },
    'dnes.stat_avg': {
        'sk': 'Priemer',
        'en': 'Average',
        'ja': 'Average',
        'zh': 'Average',
        'ru': 'Average',
        'es': 'Average',
        'de': 'Average',
        'fr': 'Average',
        'pt': 'Average',
    },
    'dnes.stat_max': {
        'sk': 'Najvyšší',
        'en': 'Highest',
        'ja': 'Highest',
        'zh': 'Highest',
        'ru': 'Highest',
        'es': 'Highest',
        'de': 'Highest',
        'fr': 'Highest',
        'pt': 'Highest',
    },
    'dnes.stat_over': {
        'sk': 'Nad hranicou',
        'en': 'Over the limit',
        'ja': 'Over the limit',
        'zh': 'Over the limit',
        'ru': 'Over the limit',
        'es': 'Over the limit',
        'de': 'Over the limit',
        'fr': 'Over the limit',
        'pt': 'Over the limit',
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
        'sk': 'Doladiť veľkosť a polohu vizuálov…',
        'en': 'Fine-tune size and position…',
        'ja': 'Fine-tune size and position…',
        'zh': 'Fine-tune size and position…',
        'ru': 'Fine-tune size and position…',
        'es': 'Fine-tune size and position…',
        'de': 'Fine-tune size and position…',
        'fr': 'Fine-tune size and position…',
        'pt': 'Fine-tune size and position…',
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
    'settings.language_sub': {
        'sk': 'Mení sa aj jazyk ukážkových hlások.',
        'en': 'Also changes the language of the sample phrases.',
        'ja': 'Also changes the language of the sample phrases.',
        'zh': 'Also changes the language of the sample phrases.',
        'ru': 'Also changes the language of the sample phrases.',
        'es': 'Also changes the language of the sample phrases.',
        'de': 'Also changes the language of the sample phrases.',
        'fr': 'Also changes the language of the sample phrases.',
        'pt': 'Also changes the language of the sample phrases.',
    },
    'settings.behaviour_title': {
        'sk': 'Správanie',
        'en': 'Behaviour',
        'ja': 'Behaviour',
        'zh': 'Behaviour',
        'ru': 'Behaviour',
        'es': 'Behaviour',
        'de': 'Behaviour',
        'fr': 'Behaviour',
        'pt': 'Behaviour',
    },
    'settings.strict_global_lock_short': {
        'sk': 'Naraz len jedna pripomienka',
        'en': 'One reminder at a time',
        'ja': 'One reminder at a time',
        'zh': 'One reminder at a time',
        'ru': 'One reminder at a time',
        'es': 'One reminder at a time',
        'de': 'One reminder at a time',
        'fr': 'One reminder at a time',
        'pt': 'One reminder at a time',
    },
    'settings.strict_global_lock_sub': {
        'sk': 'Kým jedna hrá, ostatné spúšťače mlčia — inak sa v hustej prestrelke prekrývajú.',
        'en': 'While one plays, the others stay silent — otherwise they overlap in a busy firefight.',
        'ja': 'While one plays, the others stay silent — otherwise they overlap in a busy firefight.',
        'zh': 'While one plays, the others stay silent — otherwise they overlap in a busy firefight.',
        'ru': 'While one plays, the others stay silent — otherwise they overlap in a busy firefight.',
        'es': 'While one plays, the others stay silent — otherwise they overlap in a busy firefight.',
        'de': 'While one plays, the others stay silent — otherwise they overlap in a busy firefight.',
        'fr': 'While one plays, the others stay silent — otherwise they overlap in a busy firefight.',
        'pt': 'While one plays, the others stay silent — otherwise they overlap in a busy firefight.',
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
        'en': 'A short note on each built-in reminder — what happens in the body and why it may help.',
        'ja': '基本のリマインダーそれぞれについての短い説明 — 体で何が起きているか、なぜ役立つかもしれないか。',
        'zh': '对每条基础提醒的简短说明——身体里发生了什么，以及为什么可能有帮助。',
        'ru': 'Короткое пояснение к каждому базовому напоминанию — что происходит в теле и почему это может помочь.',
        'es': 'Una breve explicación de cada recordatorio básico — qué pasa en el cuerpo y por qué puede ayudar.',
        'de': 'Eine kurze Erklärung zu jeder Grund-Erinnerung — was im Körper passiert und warum es helfen kann.',
        'fr': 'Une courte explication pour chaque rappel de base — ce qui se passe dans le corps et pourquoi ça peut aider.',
        'pt': 'Uma breve explicação de cada lembrete básico — o que acontece no corpo e por que pode ajudar.',
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
        'sk': 'Appka kreslí vlastné priehľadné okno a nič viac. Nevstupuje do procesu hry, nehookuje vykresľovanie, nečíta pamäť hry ani obsah obrazovky. Počas hry okno neberie klik ani zameranie (kliky berie len v teste vizuálu, kým ho ťaháš myšou) a nie je v Alt+Tab. Zámerne sa neskrýva pred screenshotmi ani OBS — to robia podvodné prekrytia. Záruku, že ťa anti-cheat nezablokuje, však môže dať len jeho výrobca.',
        'en': "The app draws its own transparent window and nothing more. It never enters the game process, never hooks rendering, never reads game memory or screen contents. During play the window takes no clicks or focus (it only takes clicks in the visual test, while you drag it with the mouse) and stays out of Alt+Tab. It deliberately does not hide from screenshots or OBS - that is what cheating overlays do. Only the maker of an anti-cheat can guarantee it won't flag you, though.",
        'ja': 'アプリは自分専用の透明なウィンドウを描くだけです。ゲームのプロセスに入り込むことも、描画をフックすることも、ゲームのメモリや画面の内容を読むこともありません。プレイ中、このウィンドウはクリックもフォーカスも受け取らず（クリックを受け取るのは、ビジュアルのテスト中にマウスでドラッグしているときだけ）、Alt+Tab にも出てきません。スクリーンショットや OBS から意図的に隠れることもしません — それは不正なオーバーレイがすることです。ただし、アンチチートにブロックされないと保証できるのは、そのメーカーだけです。',
        'zh': '应用只绘制自己的透明窗口，仅此而已。它不进入游戏进程，不挂钩（hook）渲染，不读取游戏内存或屏幕内容。游戏过程中，这个窗口不接收点击也不获取焦点（只有在视觉测试中、你用鼠标拖动它时才接收点击），也不会出现在 Alt+Tab 中。它刻意不对截图或 OBS 隐藏——那是作弊叠加层才会做的事。不过，能保证反作弊系统不会封禁你的，只有它的开发商。',
        'ru': 'Приложение рисует собственное прозрачное окно — и больше ничего. Оно не входит в процесс игры, не перехватывает рендеринг, не читает память игры и содержимое экрана. Во время игры окно не принимает клики и фокус (клики оно принимает только в тесте визуала, пока ты перетаскиваешь его мышью) и не появляется в Alt+Tab. Оно намеренно не прячется от скриншотов и OBS — так делают читерские оверлеи. Но гарантию, что анти-чит тебя не заблокирует, может дать только его производитель.',
        'es': 'La app dibuja su propia ventana transparente y nada más. No entra en el proceso del juego, no se engancha al renderizado, no lee la memoria del juego ni el contenido de la pantalla. Durante la partida, la ventana no recibe clics ni el foco (solo recibe clics en la prueba del visual, mientras la arrastras con el ratón) y no aparece en Alt+Tab. A propósito no se oculta de las capturas de pantalla ni de OBS — eso es lo que hacen las superposiciones para hacer trampas. Aun así, la garantía de que el anti-cheat no te bloquee solo puede darla su fabricante.',
        'de': 'Die App zeichnet ihr eigenes transparentes Fenster und sonst nichts. Sie greift nicht in den Spielprozess ein, hookt kein Rendering und liest weder den Speicher des Spiels noch den Bildschirminhalt. Während des Spiels nimmt das Fenster weder Klicks noch Fokus an (Klicks nimmt es nur im Visual-Test, solange du es mit der Maus ziehst) und taucht nicht in Alt+Tab auf. Es versteckt sich absichtlich nicht vor Screenshots oder OBS — das tun betrügerische Overlays. Eine Garantie, dass dich ein Anti-Cheat nicht sperrt, kann aber nur dessen Hersteller geben.',
        'fr': 'L’app dessine sa propre fenêtre transparente, rien de plus. Elle n’entre pas dans le processus du jeu, ne pose aucun hook sur le rendu, ne lit ni la mémoire du jeu ni le contenu de l’écran. Pendant le jeu, la fenêtre ne prend ni les clics ni le focus (elle ne prend les clics que pendant le test du visuel, tant que tu le fais glisser à la souris) et n’apparaît pas dans Alt+Tab. Elle ne se cache volontairement ni des captures d’écran ni d’OBS — c’est ce que font les superpositions de triche. Mais seul l’éditeur d’un anti-cheat peut garantir qu’il ne te bloquera pas.',
        'pt': 'O app desenha a própria janela transparente e nada mais. Não entra no processo do jogo, não faz hook na renderização, não lê a memória do jogo nem o conteúdo da tela. Durante o jogo, a janela não recebe cliques nem foco (só recebe cliques no teste do visual, enquanto você a arrasta com o mouse) e não aparece no Alt+Tab. De propósito, ela não se esconde de screenshots nem do OBS — é isso que fazem os overlays de cheat. Mas a garantia de que o anti-cheat não vai te bloquear só o fabricante dele pode dar.',
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

# --- hromadny vyber a odstranenie spustacov ---
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
        'sk': 'Odstrániť {n} označených spúšťačov?\n\n{list}',
        'en': 'Remove {n} selected triggers?\n\n{list}',
        'ja': 'Remove {n} selected triggers?\n\n{list}',
        'zh': 'Remove {n} selected triggers?\n\n{list}',
        'ru': 'Remove {n} selected triggers?\n\n{list}',
        'es': 'Remove {n} selected triggers?\n\n{list}',
        'de': 'Remove {n} selected triggers?\n\n{list}',
        'fr': 'Remove {n} selected triggers?\n\n{list}',
        'pt': 'Remove {n} selected triggers?\n\n{list}',
    },
    'log.slots_removed_bulk': {
        'sk': 'Odstránených spúšťačov: {n}.',
        'en': 'Removed {n} triggers.',
        'ja': 'Removed {n} triggers.',
        'zh': 'Removed {n} triggers.',
        'ru': 'Removed {n} triggers.',
        'es': 'Removed {n} triggers.',
        'de': 'Removed {n} triggers.',
        'fr': 'Removed {n} triggers.',
        'pt': 'Removed {n} triggers.',
    },
})

# --- navod na sparovanie hodiniek (WatchPairingDialog) ---
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
        'sk': 'Appka neprijíma tep priamo — tvári sa ako OBS. V telefóne potrebuješ appku, ktorá tep do OBS posiela (napr. „HeartRateOnStream for OBS“). Nastavíš ju raz a potom to už chodí samo.',
        'en': 'The app does not receive heart rate directly — it pretends to be OBS. On your phone you need an app that sends heart rate to OBS (e.g. “HeartRateOnStream for OBS“). You set it up once and then it just works.',
        'ja': 'The app does not receive heart rate directly — it pretends to be OBS. On your phone you need an app that sends heart rate to OBS (e.g. “HeartRateOnStream for OBS“). You set it up once and then it just works.',
        'zh': 'The app does not receive heart rate directly — it pretends to be OBS. On your phone you need an app that sends heart rate to OBS (e.g. “HeartRateOnStream for OBS“). You set it up once and then it just works.',
        'ru': 'The app does not receive heart rate directly — it pretends to be OBS. On your phone you need an app that sends heart rate to OBS (e.g. “HeartRateOnStream for OBS“). You set it up once and then it just works.',
        'es': 'The app does not receive heart rate directly — it pretends to be OBS. On your phone you need an app that sends heart rate to OBS (e.g. “HeartRateOnStream for OBS“). You set it up once and then it just works.',
        'de': 'The app does not receive heart rate directly — it pretends to be OBS. On your phone you need an app that sends heart rate to OBS (e.g. “HeartRateOnStream for OBS“). You set it up once and then it just works.',
        'fr': 'The app does not receive heart rate directly — it pretends to be OBS. On your phone you need an app that sends heart rate to OBS (e.g. “HeartRateOnStream for OBS“). You set it up once and then it just works.',
        'pt': 'The app does not receive heart rate directly — it pretends to be OBS. On your phone you need an app that sends heart rate to OBS (e.g. “HeartRateOnStream for OBS“). You set it up once and then it just works.',
    },
    'hr.pair_this_pc': {
        'sk': 'ADRESA A PORT TOHTO POČÍTAČA — prepíš do telefónu',
        'en': 'THIS PC\\u2019S ADDRESS AND PORT — type it into your phone',
        'ja': 'THIS PC\\u2019S ADDRESS AND PORT — type it into your phone',
        'zh': 'THIS PC\\u2019S ADDRESS AND PORT — type it into your phone',
        'ru': 'THIS PC\\u2019S ADDRESS AND PORT — type it into your phone',
        'es': 'THIS PC\\u2019S ADDRESS AND PORT — type it into your phone',
        'de': 'THIS PC\\u2019S ADDRESS AND PORT — type it into your phone',
        'fr': 'THIS PC\\u2019S ADDRESS AND PORT — type it into your phone',
        'pt': 'THIS PC\\u2019S ADDRESS AND PORT — type it into your phone',
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
        'zh': 'Open Command Prompt and type ipconfig — look for “IPv4 Address” (usually 192.168.x.x). Phone and PC must be on the same Wi‑Fi.',
        'ru': 'Open Command Prompt and type ipconfig — look for “IPv4 Address” (usually 192.168.x.x). Phone and PC must be on the same Wi‑Fi.',
        'es': 'Open Command Prompt and type ipconfig — look for “IPv4 Address” (usually 192.168.x.x). Phone and PC must be on the same Wi‑Fi.',
        'de': 'Open Command Prompt and type ipconfig — look for “IPv4 Address” (usually 192.168.x.x). Phone and PC must be on the same Wi‑Fi.',
        'fr': 'Open Command Prompt and type ipconfig — look for “IPv4 Address” (usually 192.168.x.x). Phone and PC must be on the same Wi‑Fi.',
        'pt': 'Open Command Prompt and type ipconfig — look for “IPv4 Address” (usually 192.168.x.x). Phone and PC must be on the same Wi‑Fi.',
    },
    'hr.step1_title': {
        'sk': 'Rovnaká Wi‑Fi',
        'en': 'Same Wi‑Fi',
        'ja': 'Same Wi‑Fi',
        'zh': 'Same Wi‑Fi',
        'ru': 'Same Wi‑Fi',
        'es': 'Same Wi‑Fi',
        'de': 'Same Wi‑Fi',
        'fr': 'Same Wi‑Fi',
        'pt': 'Same Wi‑Fi',
    },
    'hr.step1_body': {
        'sk': 'Telefón s hodinkami aj tento počítač musia byť na tej istej sieti. Cez mobilné dáta to nefunguje.',
        'en': 'The phone paired with your watch and this PC must be on the same network. Mobile data will not work.',
        'ja': 'The phone paired with your watch and this PC must be on the same network. Mobile data will not work.',
        'zh': 'The phone paired with your watch and this PC must be on the same network. Mobile data will not work.',
        'ru': 'The phone paired with your watch and this PC must be on the same network. Mobile data will not work.',
        'es': 'The phone paired with your watch and this PC must be on the same network. Mobile data will not work.',
        'de': 'The phone paired with your watch and this PC must be on the same network. Mobile data will not work.',
        'fr': 'The phone paired with your watch and this PC must be on the same network. Mobile data will not work.',
        'pt': 'The phone paired with your watch and this PC must be on the same network. Mobile data will not work.',
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
        'sk': 'Zo Google Play alebo App Store si stiahni appku, ktorá posiela tep do OBS — napríklad „HeartRateOnStream for OBS“. Prepoj ju so svojimi hodinkami podľa jej návodu.',
        'en': 'From Google Play or the App Store, get an app that sends heart rate to OBS — for example “HeartRateOnStream for OBS“. Connect it to your watch following its own instructions.',
        'ja': 'From Google Play or the App Store, get an app that sends heart rate to OBS — for example “HeartRateOnStream for OBS“. Connect it to your watch following its own instructions.',
        'zh': 'From Google Play or the App Store, get an app that sends heart rate to OBS — for example “HeartRateOnStream for OBS“. Connect it to your watch following its own instructions.',
        'ru': 'From Google Play or the App Store, get an app that sends heart rate to OBS — for example “HeartRateOnStream for OBS“. Connect it to your watch following its own instructions.',
        'es': 'From Google Play or the App Store, get an app that sends heart rate to OBS — for example “HeartRateOnStream for OBS“. Connect it to your watch following its own instructions.',
        'de': 'From Google Play or the App Store, get an app that sends heart rate to OBS — for example “HeartRateOnStream for OBS“. Connect it to your watch following its own instructions.',
        'fr': 'From Google Play or the App Store, get an app that sends heart rate to OBS — for example “HeartRateOnStream for OBS“. Connect it to your watch following its own instructions.',
        'pt': 'From Google Play or the App Store, get an app that sends heart rate to OBS — for example “HeartRateOnStream for OBS“. Connect it to your watch following its own instructions.',
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
    'hr.step3_body': {
        'sk': 'V appke na telefóne nájdi nastavenie OBS / WebSocket a zadaj adresu a port tohto počítača (hore v rámiku). Heslo nechaj prázdne.',
        'en': 'In the phone app, find the OBS / WebSocket setting and enter this PC\\u2019s address and port (in the box above). Leave the password empty.',
        'ja': 'In the phone app, find the OBS / WebSocket setting and enter this PC\\u2019s address and port (in the box above). Leave the password empty.',
        'zh': 'In the phone app, find the OBS / WebSocket setting and enter this PC\\u2019s address and port (in the box above). Leave the password empty.',
        'ru': 'In the phone app, find the OBS / WebSocket setting and enter this PC\\u2019s address and port (in the box above). Leave the password empty.',
        'es': 'In the phone app, find the OBS / WebSocket setting and enter this PC\\u2019s address and port (in the box above). Leave the password empty.',
        'de': 'In the phone app, find the OBS / WebSocket setting and enter this PC\\u2019s address and port (in the box above). Leave the password empty.',
        'fr': 'In the phone app, find the OBS / WebSocket setting and enter this PC\\u2019s address and port (in the box above). Leave the password empty.',
        'pt': 'In the phone app, find the OBS / WebSocket setting and enter this PC\\u2019s address and port (in the box above). Leave the password empty.',
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
        'zh': 'Once the phone app connects, it will offer a scene named “Zanshin“ and a text source named “Tep“. Select exactly those two — that is how your heart rate comes through.',
        'ru': 'Once the phone app connects, it will offer a scene named “Zanshin“ and a text source named “Tep“. Select exactly those two — that is how your heart rate comes through.',
        'es': 'Once the phone app connects, it will offer a scene named “Zanshin“ and a text source named “Tep“. Select exactly those two — that is how your heart rate comes through.',
        'de': 'Once the phone app connects, it will offer a scene named “Zanshin“ and a text source named “Tep“. Select exactly those two — that is how your heart rate comes through.',
        'fr': 'Once the phone app connects, it will offer a scene named “Zanshin“ and a text source named “Tep“. Select exactly those two — that is how your heart rate comes through.',
        'pt': 'Once the phone app connects, it will offer a scene named “Zanshin“ and a text source named “Tep“. Select exactly those two — that is how your heart rate comes through.',
    },
    'hr.step5_title': {
        'sk': 'Zapni senzor tu',
        'en': 'Turn the sensor on here',
        'ja': 'Turn the sensor on here',
        'zh': 'Turn the sensor on here',
        'ru': 'Turn the sensor on here',
        'es': 'Turn the sensor on here',
        'de': 'Turn the sensor on here',
        'fr': 'Turn the sensor on here',
        'pt': 'Turn the sensor on here',
    },
    'hr.step5_body': {
        'sk': 'Vráť sa sem, prepni „Zapnúť senzor tepu“ a sleduj stav dole. Keď sa hodinky pripoja, uvidíš svoj tep v BPM.',
        'en': 'Come back here, flip “Turn on the heart-rate sensor“ and watch the status below. When the watch connects, you will see your live BPM.',
        'ja': 'Come back here, flip “Turn on the heart-rate sensor“ and watch the status below. When the watch connects, you will see your live BPM.',
        'zh': 'Come back here, flip “Turn on the heart-rate sensor“ and watch the status below. When the watch connects, you will see your live BPM.',
        'ru': 'Come back here, flip “Turn on the heart-rate sensor“ and watch the status below. When the watch connects, you will see your live BPM.',
        'es': 'Come back here, flip “Turn on the heart-rate sensor“ and watch the status below. When the watch connects, you will see your live BPM.',
        'de': 'Come back here, flip “Turn on the heart-rate sensor“ and watch the status below. When the watch connects, you will see your live BPM.',
        'fr': 'Come back here, flip “Turn on the heart-rate sensor“ and watch the status below. When the watch connects, you will see your live BPM.',
        'pt': 'Come back here, flip “Turn on the heart-rate sensor“ and watch the status below. When the watch connects, you will see your live BPM.',
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
    'hr.trouble_body': {
        'sk': 'Skontroluj, či máš v appke na telefóne vybranú scénu „Zanshin“ a zdroj „Tep“, a či hodinky naozaj merajú (v ich appke vidíš aktuálny tep). Ak port obsadí iný program, zmeň ho tu aj v telefóne na rovnaké číslo.',
        'en': 'Check that the phone app has the “Zanshin“ scene and “Tep“ source selected, and that the watch is actually measuring (you can see a live reading in its own app). If another program takes the port, change it here and on the phone to the same number.',
        'ja': 'Check that the phone app has the “Zanshin“ scene and “Tep“ source selected, and that the watch is actually measuring (you can see a live reading in its own app). If another program takes the port, change it here and on the phone to the same number.',
        'zh': 'Check that the phone app has the “Zanshin“ scene and “Tep“ source selected, and that the watch is actually measuring (you can see a live reading in its own app). If another program takes the port, change it here and on the phone to the same number.',
        'ru': 'Check that the phone app has the “Zanshin“ scene and “Tep“ source selected, and that the watch is actually measuring (you can see a live reading in its own app). If another program takes the port, change it here and on the phone to the same number.',
        'es': 'Check that the phone app has the “Zanshin“ scene and “Tep“ source selected, and that the watch is actually measuring (you can see a live reading in its own app). If another program takes the port, change it here and on the phone to the same number.',
        'de': 'Check that the phone app has the “Zanshin“ scene and “Tep“ source selected, and that the watch is actually measuring (you can see a live reading in its own app). If another program takes the port, change it here and on the phone to the same number.',
        'fr': 'Check that the phone app has the “Zanshin“ scene and “Tep“ source selected, and that the watch is actually measuring (you can see a live reading in its own app). If another program takes the port, change it here and on the phone to the same number.',
        'pt': 'Check that the phone app has the “Zanshin“ scene and “Tep“ source selected, and that the watch is actually measuring (you can see a live reading in its own app). If another program takes the port, change it here and on the phone to the same number.',
    },
})

# --- "preco to funguje" na stranke Dnes ---
STRINGS.update({
    'dnes.why_line': {
        'sk': 'Telo v hre stuhne skôr, než si to všimneš — Zanshin na to naviaže krátky reset.',
        'en': 'Your body tenses up mid-game before you notice — Zanshin ties a short reset to that.',
        'ja': 'Your body tenses up mid-game before you notice — Zanshin ties a short reset to that.',
        'zh': 'Your body tenses up mid-game before you notice — Zanshin ties a short reset to that.',
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

# --- drag-test vizualov, farba piktogramu, Guide v menu ---
STRINGS.update({
    'nav.cmdk_hint': {
        # tlacidlo v bocnom paneli (Ctrl+K) - bolo hardcodovane po slovensky
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
        'sk': 'Klikni na „Test“ a piktogram sa zobrazí na obrazovke — chyť ho myšou a potiahni, kam chceš. Druhým klikom polohu uložíš.',
        'en': 'Click “Test” and the icon appears on screen — grab it with the mouse and drag it wherever you want. Click again to save the position.',
        'ja': 'Click “Test” and the icon appears on screen — grab it with the mouse and drag it wherever you want. Click again to save the position.',
        'zh': 'Click “Test” and the icon appears on screen — grab it with the mouse and drag it wherever you want. Click again to save the position.',
        'ru': 'Click “Test” and the icon appears on screen — grab it with the mouse and drag it wherever you want. Click again to save the position.',
        'es': 'Click “Test” and the icon appears on screen — grab it with the mouse and drag it wherever you want. Click again to save the position.',
        'de': 'Click “Test” and the icon appears on screen — grab it with the mouse and drag it wherever you want. Click again to save the position.',
        'fr': 'Click “Test” and the icon appears on screen — grab it with the mouse and drag it wherever you want. Click again to save the position.',
        'pt': 'Click “Test” and the icon appears on screen — grab it with the mouse and drag it wherever you want. Click again to save the position.',
    },
    'overlay.color_title': {
        'sk': 'Farba piktogramu',
        'en': 'Icon colour',
        'ja': 'アイコンの色',
        'zh': '图标颜色',
        'ru': 'Цвет значка',
        'es': 'Color del icono',
        'de': 'Symbolfarbe',
        'fr': "Couleur de l'icône",
        'pt': 'Cor do ícone',
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
    'nav.guide': {
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
})

# --- prepracovany onboarding (4 kroky s obrazom; od 0.2 piaty: styl hlasky) ---
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
    # 0.2: appka ucinok nepotvrdzuje (tiche rameno ho ma len zistit) -
    # "chce ti pomoct", nie "trenuje ta".
    'ob.step1.body': {
        'sk': 'Pri clutchi telo stuhne skôr, než si to všimneš — zovretá čeľusť, zadržaný dych, kŕč v ruke. Zanshin netrénuje aim; chce ti pomôcť odísť z hry pokojnejší, než si do nej vošiel.',
        'en': "In a clutch your body tightens before you notice — a clenched jaw, a held breath, a cramped hand. Zanshin doesn't train your aim; it's meant to help you leave the match calmer than you entered it.",
        'ja': 'クラッチの場面では、気づく前に体がこわばります — 食いしばった顎、止めた息、手のこわばり。Zanshin はエイムを鍛えるものではありません。ゲームを始めたときより穏やかな状態で終えられるよう、手助けしたいのです。',
        'zh': '残局关头，身体会在你察觉之前就僵住——咬紧的下颌、屏住的呼吸、抽紧的手。Zanshin 不训练瞄准；它想帮你离开游戏时比进去时更平静。',
        'ru': 'В клатче тело напрягается раньше, чем ты это заметишь, — сжатая челюсть, задержанное дыхание, судорога в руке. Zanshin не тренирует аим; его задача — помочь тебе выйти из игры спокойнее, чем ты в неё вошёл.',
        'es': 'En un clutch el cuerpo se tensa antes de que lo notes — la mandíbula apretada, la respiración contenida, la mano agarrotada. Zanshin no entrena tu puntería; quiere ayudarte a salir de la partida más tranquilo de lo que entraste.',
        'de': 'Im Clutch verspannt sich der Körper, bevor du es merkst — zusammengebissener Kiefer, angehaltener Atem, verkrampfte Hand. Zanshin trainiert nicht dein Zielen; es will dir helfen, das Spiel ruhiger zu verlassen, als du es betreten hast.',
        'fr': 'Dans un clutch, ton corps se crispe avant que tu le remarques — mâchoire serrée, souffle retenu, crampe dans la main. Zanshin n’entraîne pas ta visée ; il veut t’aider à quitter la partie plus calme que tu n’y es entré.',
        'pt': 'Num clutch, o corpo trava antes de você perceber — mandíbula cerrada, respiração presa, câimbra na mão. O Zanshin não treina a sua mira; ele quer te ajudar a sair do jogo mais calmo do que entrou.',
    },
    'ob.step1.cap_grounding': {
        'sk': 'Ťažisko',
        'en': 'Grounding',
        'ja': 'Grounding',
        'zh': 'Grounding',
        'ru': 'Grounding',
        'es': 'Grounding',
        'de': 'Grounding',
        'fr': 'Grounding',
        'pt': 'Grounding',
    },
    'ob.step1.cap_jaw': {
        'sk': 'Uvoľni čeľusť',
        'en': 'Unclench',
        'ja': 'Unclench',
        'zh': 'Unclench',
        'ru': 'Unclench',
        'es': 'Unclench',
        'de': 'Unclench',
        'fr': 'Unclench',
        'pt': 'Unclench',
    },
    'ob.step1.cap_breath': {
        'sk': 'Dych',
        'en': 'Breath',
        'ja': 'Breath',
        'zh': 'Breath',
        'ru': 'Breath',
        'es': 'Breath',
        'de': 'Breath',
        'fr': 'Breath',
        'pt': 'Breath',
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
        'sk': 'Preskočiť úvod',
        'en': 'Skip intro',
        'ja': 'Skip intro',
        'zh': 'Skip intro',
        'ru': 'Skip intro',
        'es': 'Skip intro',
        'de': 'Skip intro',
        'fr': 'Skip intro',
        'pt': 'Skip intro',
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
        'sk': 'Nenápadné. V rohu, mimo cesty.',
        'en': 'Unobtrusive. In a corner, out of the way.',
        'ja': 'Unobtrusive. In a corner, out of the way.',
        'zh': 'Unobtrusive. In a corner, out of the way.',
        'ru': 'Unobtrusive. In a corner, out of the way.',
        'es': 'Unobtrusive. In a corner, out of the way.',
        'de': 'Unobtrusive. In a corner, out of the way.',
        'fr': 'Unobtrusive. In a corner, out of the way.',
        'pt': 'Unobtrusive. In a corner, out of the way.',
    },
    'ob.step2.body': {
        'sk': 'Pripomienky sa objavia na okraji obrazovky a zase zmiznú — neprekrývajú zameriavač ani killfeed. Všetko sa dá potiahnuť tam, kam chceš, a v hre cez to klik prejde do hry.',
        'en': 'Cues appear at the edge of the screen and fade away — they never cover your crosshair or killfeed. Everything can be dragged where you want it, and in-game your clicks pass straight through to the game.',
        'ja': 'Cues appear at the edge of the screen and fade away — they never cover your crosshair or killfeed. Everything can be dragged where you want it, and in-game your clicks pass straight through to the game.',
        'zh': 'Cues appear at the edge of the screen and fade away — they never cover your crosshair or killfeed. Everything can be dragged where you want it, and in-game your clicks pass straight through to the game.',
        'ru': 'Cues appear at the edge of the screen and fade away — they never cover your crosshair or killfeed. Everything can be dragged where you want it, and in-game your clicks pass straight through to the game.',
        'es': 'Cues appear at the edge of the screen and fade away — they never cover your crosshair or killfeed. Everything can be dragged where you want it, and in-game your clicks pass straight through to the game.',
        'de': 'Cues appear at the edge of the screen and fade away — they never cover your crosshair or killfeed. Everything can be dragged where you want it, and in-game your clicks pass straight through to the game.',
        'fr': 'Cues appear at the edge of the screen and fade away — they never cover your crosshair or killfeed. Everything can be dragged where you want it, and in-game your clicks pass straight through to the game.',
        'pt': 'Cues appear at the edge of the screen and fade away — they never cover your crosshair or killfeed. Everything can be dragged where you want it, and in-game your clicks pass straight through to the game.',
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
        'sk': 'KROK 3 z 5 — nepovinné',
        'en': 'STEP 3 of 5 — optional',
        'ja': 'ステップ 3 / 5 — 任意',
        'zh': '第 3 步，共 5 步 — 可选',
        'ru': 'ШАГ 3 из 5 — необязательно',
        'es': 'PASO 3 de 5 — opcional',
        'de': 'SCHRITT 3 von 5 — optional',
        'fr': 'ÉTAPE 3 sur 5 — facultatif',
        'pt': 'PASSO 3 de 5 — opcional',
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
        'sk': 'Kedy sa ozvať, rozhoduje tvoj tep — bez neho appka nemá z čoho poznať, že ti záťaž drží hore, a nepovie nič. Spárovať sa dá aj neskôr na stránke „V hre“.',
        'en': 'Your heart rate decides when to speak — without it the app has no way to know your load is up, and says nothing. You can pair later on the “In-game” page.',
        'ja': 'いつ声をかけるかは、あなたの心拍が決めます — 心拍がなければ、アプリには負荷が高いままだと知る手がかりがなく、何も言いません。時計は「ゲーム中」ページであとからでもつなげます。',
        'zh': '什么时候出声，由你的心率决定——没有心率，应用就无从得知你的负荷一直偏高，也就什么都不会说。之后也可以在“游戏中”页面配对。',
        'ru': 'Когда подать голос, решает твой пульс — без него приложению не из чего понять, что нагрузка держится высокой, и оно ничего не скажет. Подключить часы можно и позже на странице «В игре».',
        'es': 'Cuándo hablar lo decide tu pulso — sin él, la app no tiene cómo saber que tu carga se mantiene alta, y no dice nada. También puedes vincular el reloj más tarde en la página «En el juego».',
        'de': 'Wann sich die App meldet, entscheidet dein Puls — ohne ihn kann sie nicht erkennen, dass deine Last oben bleibt, und sagt nichts. Verbinden kannst du auch später auf der Seite „Im Spiel“.',
        'fr': 'C’est ton pouls qui décide quand l’app se manifeste — sans lui, elle n’a aucun moyen de savoir que ta charge reste haute, et elle ne dit rien. Tu peux aussi connecter la montre plus tard, sur la page « En jeu ».',
        'pt': 'Quem decide quando avisar é o seu pulso — sem ele, o app não tem como saber que a sua carga está alta e não diz nada. Dá para parear depois, na página “No jogo”.',
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
    'ob.step3.later': {
        'sk': 'Preskočiť — spárujem neskôr',
        'en': "Skip — I'll pair later",
        'ja': "Skip — I'll pair later",
        'zh': "Skip — I'll pair later",
        'ru': "Skip — I'll pair later",
        'es': "Skip — I'll pair later",
        'de': "Skip — I'll pair later",
        'fr': "Skip — I'll pair later",
        'pt': "Skip — I'll pair later",
    },
    'ob.step3.later_note': {
        'sk': 'Nájdeš to kedykoľvek vo „V hre → Ako spárovať hodinky“.',
        'en': "You'll find it any time under “In game -> How to pair your watch“.",
        'ja': "You'll find it any time under “In game -> How to pair your watch“.",
        'zh': "You'll find it any time under “In game -> How to pair your watch“.",
        'ru': "You'll find it any time under “In game -> How to pair your watch“.",
        'es': "You'll find it any time under “In game -> How to pair your watch“.",
        'de': "You'll find it any time under “In game -> How to pair your watch“.",
        'fr': "You'll find it any time under “In game -> How to pair your watch“.",
        'pt': "You'll find it any time under “In game -> How to pair your watch“.",
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

# --- guided tour (prehliadka appky) ---
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
        'sk': 'Ukážem ti, kde čo je — trvá to pár sekúnd. Kedykoľvek môžeš kliknúť Preskočiť.',
        'en': 'Let me show you where things are — it takes a few seconds. You can hit Skip any time.',
        'ja': 'Let me show you where things are — it takes a few seconds. You can hit Skip any time.',
        'zh': 'Let me show you where things are — it takes a few seconds. You can hit Skip any time.',
        'ru': 'Let me show you where things are — it takes a few seconds. You can hit Skip any time.',
        'es': 'Let me show you where things are — it takes a few seconds. You can hit Skip any time.',
        'de': 'Let me show you where things are — it takes a few seconds. You can hit Skip any time.',
        'fr': 'Let me show you where things are — it takes a few seconds. You can hit Skip any time.',
        'pt': 'Let me show you where things are — it takes a few seconds. You can hit Skip any time.',
    },
    'tour.kamae.title': {
        'sk': 'Spustiť a zastaviť',
        'en': 'Start and stop',
        'ja': 'Start and stop',
        'zh': 'Start and stop',
        'ru': 'Start and stop',
        'es': 'Start and stop',
        'de': 'Start and stop',
        'fr': 'Start and stop',
        'pt': 'Start and stop',
    },
    'tour.kamae.body': {
        'sk': 'Tento pás je hlavný vypínač. Vľavo má tlačidlo ▶ / ▮▮ — tým sa appka spúšťa a zastavuje. Keď počúva, pás jemne dýcha; keď stojí, je pokojný.',
        'en': 'This bar is the main switch. The ▶ / ▮▮ button on the left starts and stops the app. While it listens the bar breathes gently; when stopped it is still.',
        'ja': 'This bar is the main switch. The ▶ / ▮▮ button on the left starts and stops the app. While it listens the bar breathes gently; when stopped it is still.',
        'zh': 'This bar is the main switch. The ▶ / ▮▮ button on the left starts and stops the app. While it listens the bar breathes gently; when stopped it is still.',
        'ru': 'This bar is the main switch. The ▶ / ▮▮ button on the left starts and stops the app. While it listens the bar breathes gently; when stopped it is still.',
        'es': 'This bar is the main switch. The ▶ / ▮▮ button on the left starts and stops the app. While it listens the bar breathes gently; when stopped it is still.',
        'de': 'This bar is the main switch. The ▶ / ▮▮ button on the left starts and stops the app. While it listens the bar breathes gently; when stopped it is still.',
        'fr': 'This bar is the main switch. The ▶ / ▮▮ button on the left starts and stops the app. While it listens the bar breathes gently; when stopped it is still.',
        'pt': 'This bar is the main switch. The ▶ / ▮▮ button on the left starts and stops the app. While it listens the bar breathes gently; when stopped it is still.',
    },
    'tour.triggers.title': {
        'sk': 'Spúšťače',
        'en': 'Triggers',
        'ja': 'Triggers',
        'zh': 'Triggers',
        'ru': 'Triggers',
        'es': 'Triggers',
        'de': 'Triggers',
        'fr': 'Triggers',
        'pt': 'Triggers',
    },
    # 0.2 (stress-gate): uz nie „v najbližšej prestávke" - hlas ide len v
    # prestávke, keď záťaž nestúpa, a v kritickom pásme mlčí. Ostatných 7
    # jazykov je zatiaľ anglicky (rovnako ako `_sk_en`, ktorý tu ešte nie je).
    'tour.triggers.body': {
        'sk': 'Tu si nastavíš, ČO appka povie — vetu, hlas a zvuk. KEDY sa ozve, rozhoduje tvoje telo: appka počká, kým ti záťaž chvíľu drží hore, a ozve sa v prestávke, keď už záťaž nestúpa; kým je tep v pásme Špička, mlčí. Hore vidíš, s akými číslami práve počíta — nenastavuješ ich, hranicu si appka dolaďuje z tvojich relácií. Prečo práve tieto štyri veci, si rozbalíš šípkou pri každej hláške.',
        'en': 'Here you set WHAT the app says — the line, the voice and the sound. WHEN it speaks is up to your body: it waits until your load holds up for a while, then speaks in a break once the load has stopped climbing; while your pulse is in the peak zone, it stays quiet. At the top you see the numbers it is using right now — you do not set them; the app tunes its threshold from your sessions. Why these four things in particular, you can unfold with the arrow at each cue.',
        'ja': 'ここで設定するのは、アプリが「何を」言うかです — 言葉、音声、効果音。「いつ」声をかけるかは、あなたの体が決めます。アプリは負荷がしばらく高いまま続くのを待ち、負荷がもう上がっていない合間に声をかけます。心拍が「ピーク」の帯にある間は黙っています。上には、アプリが今使っている数値が表示されます — これは設定するものではなく、しきい値はアプリがあなたのセッションから調整していきます。なぜこの4つなのかは、各合図の矢印で開いて読めます。',
        'zh': '在这里设置应用说“什么”——台词、语音和音效。“什么时候”出声，由你的身体决定：应用会等负荷持续偏高一阵子，然后在负荷不再上升的间歇里出声；心率处于高峰区间时，它保持安静。顶部显示它当前使用的数值——这些不用你设置，应用会根据你的记录微调阈值。为什么偏偏是这四件事，点每条提示旁的箭头就能展开看。',
        'ru': 'Здесь ты настраиваешь, ЧТО скажет приложение, — фразу, голос и звук. КОГДА оно подаст голос, решает твоё тело: приложение ждёт, пока нагрузка какое-то время продержится высокой, и подаёт голос в паузе, когда нагрузка уже не растёт; пока пульс в пиковой зоне, оно молчит. Вверху видно, с какими числами оно считает прямо сейчас, — их ты не настраиваешь, порог приложение уточняет по твоим сессиям. Почему именно эти четыре вещи, раскроешь стрелкой у каждой подсказки.',
        'es': 'Aquí ajustas QUÉ dice la app — la frase, la voz y el sonido. CUÁNDO habla lo decide tu cuerpo: la app espera a que tu carga se mantenga alta un rato y habla en una pausa, cuando la carga ya no sube; mientras el pulso está en la zona de pico, guarda silencio. Arriba ves con qué números cuenta ahora mismo — no los ajustas tú; la app afina el umbral a partir de tus sesiones. Por qué precisamente estas cuatro cosas, lo despliegas con la flecha de cada aviso.',
        'de': 'Hier stellst du ein, WAS die App sagt — den Satz, die Stimme und den Ton. WANN sie sich meldet, entscheidet dein Körper: Die App wartet, bis deine Last eine Weile oben bleibt, und meldet sich in einer Pause, wenn die Last nicht mehr steigt; solange dein Puls im Spitzenbereich ist, schweigt sie. Oben siehst du, mit welchen Zahlen sie gerade rechnet — du stellst sie nicht ein, die Schwelle stimmt die App anhand deiner Sitzungen fein ab. Warum gerade diese vier Dinge, klappst du mit dem Pfeil bei jedem Hinweis auf.',
        'fr': 'Ici, tu règles CE QUE l’app dit — la phrase, la voix et le son. QUAND elle se manifeste, c’est ton corps qui le décide : l’app attend que ta charge reste haute un moment, puis se manifeste pendant une pause, quand la charge ne monte plus ; tant que ton pouls est en zone de pic, elle se tait. En haut, tu vois sur quels chiffres elle se base en ce moment — tu ne les règles pas, l’app affine son seuil à partir de tes séances. Pourquoi justement ces quatre choses, tu peux le déplier avec la flèche à côté de chaque rappel.',
        'pt': 'Aqui você define O QUE o app diz — a frase, a voz e o som. QUANDO ele avisa, quem decide é o seu corpo: o app espera até a sua carga se manter alta por um tempo e avisa numa pausa, quando a carga já não está subindo; enquanto o pulso está na zona de pico, fica em silêncio. No topo você vê com que números ele está trabalhando agora — você não os define; o app ajusta o limiar a partir das suas sessões. Por que justamente essas quatro coisas, você descobre abrindo a seta ao lado de cada aviso.',
    },
    'tour.sound.title': {
        'sk': 'Zvuk',
        'en': 'Sound',
        'ja': 'Sound',
        'zh': 'Sound',
        'ru': 'Sound',
        'es': 'Sound',
        'de': 'Sound',
        'fr': 'Sound',
        'pt': 'Sound',
    },
    'tour.sound.body': {
        'sk': 'Hlas, rýchlosť reči a hlasitosť pripomienok — aj pomer medzi zvukom a hlasom. Vlastnú nahrávku pridáš pri konkrétnej hláške na stránke Spúšťače.',
        'en': 'The voice, speech speed and volume of the cues — and the mix between sound and voice. You add your own recording on a specific cue, on the Triggers page.',
        'ja': '音声、話す速さ、リマインダーの音量 — そして効果音と音声のバランスも。自分の録音は、「トリガー」ページで個々の合図に追加します。',
        'zh': '提醒的语音、语速和音量——还有音效与语音之间的比例。自己的录音可以在“触发器”页面里对应的提示上添加。',
        'ru': 'Голос, скорость речи и громкость напоминаний — и баланс между звуком и голосом. Свою запись добавляешь у конкретной подсказки на странице «Триггеры».',
        'es': 'La voz, la velocidad del habla y el volumen de los recordatorios — y también la mezcla entre sonido y voz. Tu propia grabación la añades en un aviso concreto, en la página Disparadores.',
        'de': 'Stimme, Sprechtempo und Lautstärke der Erinnerungen — auch das Verhältnis zwischen Ton und Stimme. Eine eigene Aufnahme fügst du bei einem bestimmten Hinweis auf der Seite Trigger hinzu.',
        'fr': 'La voix, la vitesse de parole et le volume des rappels — et aussi l’équilibre entre le son et la voix. Tu ajoutes ton propre enregistrement sur un rappel précis, dans la page Déclencheurs.',
        'pt': 'A voz, a velocidade da fala e o volume dos lembretes — e também a mistura entre som e voz. Uma gravação sua você adiciona num aviso específico, na página Gatilhos.',
    },
    'tour.ingame.title': {
        'sk': 'V hre',
        'en': 'In game',
        'ja': 'In game',
        'zh': 'In game',
        'ru': 'In game',
        'es': 'In game',
        'de': 'In game',
        'fr': 'In game',
        'pt': 'In game',
    },
    'tour.ingame.body': {
        'sk': 'Tu spáruješ hodinky a nastavíš piktogramy, ktoré appka kreslí počas hrania — a potiahneš si ich tam, kam chceš. Panel s tepom v hre nájdeš v Nastaveniach → Všeobecné.',
        'en': 'Here you pair your watch and set up the icons the app draws while you play — and drag them wherever you want. The in-game heart-rate panel is in Settings → General.',
        'ja': 'ここで時計をつなぎ、プレイ中にアプリが描くアイコンを設定します — そして好きな場所へドラッグできます。ゲーム中の心拍パネルは「設定」→「全般」にあります。',
        'zh': '在这里配对手表，设置应用在你玩游戏时绘制的图标——还能把它们拖到你想要的位置。游戏中的心率面板在“设置 → 通用”里。',
        'ru': 'Здесь ты подключаешь часы и настраиваешь значки, которые приложение рисует во время игры, — и перетаскиваешь их, куда хочешь. Панель с пульсом в игре найдёшь в Настройках → Общие.',
        'es': 'Aquí vinculas el reloj y configuras los iconos que la app dibuja mientras juegas — y los arrastras adonde quieras. El panel de pulso en el juego está en Ajustes → General.',
        'de': 'Hier verbindest du die Uhr und stellst die Symbole ein, die die App beim Spielen zeichnet — und ziehst sie dahin, wo du sie haben willst. Das Puls-Panel im Spiel findest du unter Einstellungen → Allgemein.',
        'fr': 'Ici, tu connectes ta montre et tu règles les icônes que l’app dessine pendant que tu joues — et tu les fais glisser où tu veux. Le panneau de pouls en jeu se trouve dans Paramètres → Général.',
        'pt': 'Aqui você pareia o relógio e configura os ícones que o app desenha enquanto você joga — e os arrasta para onde quiser. O painel de pulso no jogo fica em Configurações → Geral.',
    },
    # Predtym opisoval QuickDock tlacidlo Spustit/Zastavit, ktore redizajn
    # "Sumi noc" zrusil - jedinym ovladacom spusti/zastav je teraz enso v
    # strede sidebaru. Text prepisany na enso (klucove mena ostavaju,
    # aby sa nemenili odkazy na tento krok). `_sk_en` este nie je v tomto
    # bode suboru definovane (definuje sa nizsie), preto plny slovnik ako
    # ostatne zaznamy v tomto bloku - ostatne jazyky su docasne = en, viz
    # preklad_TODO.csv (rovnaky stav ako predtym).
    'tour.dock.title': {
        'sk': 'Spusti a zastav',
        'en': 'Start and stop',
        'ja': 'Start and stop',
        'zh': 'Start and stop',
        'ru': 'Start and stop',
        'es': 'Start and stop',
        'de': 'Start and stop',
        'fr': 'Start and stop',
        'pt': 'Start and stop',
    },
    'tour.dock.body': {
        'sk': 'Toto je ensō — značka appky a zároveň jej stav. Zelené a dýchajúce znamená, že appka počúva; červené a nehybné, že je zastavená. Keď telo drží hore, objaví sa vnútri pomalý prstenec — to znamená, že appka čaká na vhodnú chvíľu. Žije na tejto stránke; na ostatných nájdeš stav ako farebnú bodku v paneli vľavo.',
        'en': "This is the ensō — the app's mark and its state in one. Green and breathing means it is listening; red and still means it is stopped. When your body stays up, a slow ring appears inside it — that means the app is waiting for a good moment. It lives on this page; elsewhere the coloured dot in the left rail carries the state.",
        'ja': "This is the ensō — the app's mark and its state in one. Green and breathing means it is listening; red and still means it is stopped. When your body stays up, a slow ring appears inside it — that means the app is waiting for a good moment. It lives on this page; elsewhere the coloured dot in the left rail carries the state.",
        'zh': "This is the ensō — the app's mark and its state in one. Green and breathing means it is listening; red and still means it is stopped. When your body stays up, a slow ring appears inside it — that means the app is waiting for a good moment. It lives on this page; elsewhere the coloured dot in the left rail carries the state.",
        'ru': "This is the ensō — the app's mark and its state in one. Green and breathing means it is listening; red and still means it is stopped. When your body stays up, a slow ring appears inside it — that means the app is waiting for a good moment. It lives on this page; elsewhere the coloured dot in the left rail carries the state.",
        'es': "This is the ensō — the app's mark and its state in one. Green and breathing means it is listening; red and still means it is stopped. When your body stays up, a slow ring appears inside it — that means the app is waiting for a good moment. It lives on this page; elsewhere the coloured dot in the left rail carries the state.",
        'de': "This is the ensō — the app's mark and its state in one. Green and breathing means it is listening; red and still means it is stopped. When your body stays up, a slow ring appears inside it — that means the app is waiting for a good moment. It lives on this page; elsewhere the coloured dot in the left rail carries the state.",
        'fr': "This is the ensō — the app's mark and its state in one. Green and breathing means it is listening; red and still means it is stopped. When your body stays up, a slow ring appears inside it — that means the app is waiting for a good moment. It lives on this page; elsewhere the coloured dot in the left rail carries the state.",
        'pt': "This is the ensō — the app's mark and its state in one. Green and breathing means it is listening; red and still means it is stopped. When your body stays up, a slow ring appears inside it — that means the app is waiting for a good moment. It lives on this page; elsewhere the coloured dot in the left rail carries the state.",
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
    """sk + en rucne, ostatne jazyky zatial anglicky (na dopreklad -
    zoznam v preklad_TODO.csv). Rovnaka konvencia ako doteraz, len bez
    jedenastich riadkov na kazdy kluc. Preklad do ja..pt doplna `_tr7`,
    cestinu a bulharcinu modul `i18n_cs_bg.py` (koniec suboru)."""
    return {"sk": sk, "en": en, "ja": en, "zh": en, "ru": en, "es": en,
            "de": en, "fr": en, "pt": en, "cs": en, "bg": en}


# --- historia relacii tepu, metriky z pulzu, odporucania, zdroje k tepu ---
# Texty metrik su presne znenie zo zadania (pre hraca, nie pre lekara).
# Nikde "HRV" ako nieco, co appka meria; nikde zdravotna diagnoza.
STRINGS.update({
    'nav.historia': _sk_en('História', 'History'),
    'history.title': _sk_en('História relácií', 'Session history'),
    'history.subtitle': _sk_en(
        'Každá relácia so senzorom tepu (aspoň minúta) sa uloží sem. Metriky sú z čistého tepu — nie HRV.',
        'Every heart-rate session (at least a minute) is saved here. Metrics come from plain heart rate — not HRV.'),
    'history.empty': _sk_en(
        'Zatiaľ žiadna relácia. Na stránke „V hre“ zapni „Počúvať tep z hodiniek“, spusti appku tlačidlom ▶ na stránke Dnes a zahraj si aspoň minútu — po zastavení sa relácia objaví tu.',
        'No sessions yet. Turn on “Listen for heart rate from the watch” on the “In-game” page, start the app with ▶ on the Today page and play for at least a minute — once you stop, the session shows up here.'),
    'history.insights_title': _sk_en('Čo si appka všimla', 'What the app noticed'),
    # B3-worlds: postrehy sa rataju len zo sveta, ktory je prave zapnuty -
    # "z celej historie" by uz nebola pravda (stare preklady zmazane).
    'history.insights_note': _sk_en(
        'Počíta sa na pozadí z histórie tohto sveta. Sú to postrehy a tipy, nie diagnózy.',
        "Computed in the background from this world's history. Observations and tips, not diagnoses."),
    'history.analysis_running': _sk_en('Analyzujem históriu…', 'Analysing history…'),
    'history.analysis_stamp': _sk_en('Analýza z {when}', 'Analysis from {when}'),
    'history.recompute': _sk_en('Prepočítať', 'Recompute'),
    'history.trend_title': _sk_en('Vývoj naprieč reláciami', 'Trend across sessions'),
    'history.trend_baseline': _sk_en('Pokojová základňa (BPM) po reláciách — staršie vľavo',
                                     'Resting baseline (BPM) per session — oldest on the left'),
    'history.trend_avg': _sk_en('Priemerný tep (BPM) po reláciách — staršie vľavo',
                                'Average heart rate (BPM) per session — oldest on the left'),
    'history.trend_delta': _sk_en('{first} → {last} BPM, trend {slope:+.1f} BPM/týždeň',
                                  '{first} → {last} BPM, trend {slope:+.1f} BPM/week'),
    'history.trend_need_more': _sk_en(
        'Relácie sú zatiaľ príliš blízko pri sebe na trend — over o pár dní.',
        'Sessions are still too close together for a trend — check back in a few days.'),
    'history.trend_simple_delta': _sk_en('{first} → {last}', '{first} → {last}'),
    'history.empty_period': _sk_en('V tomto období zatiaľ nič.', 'Nothing in this period yet.'),
    'history.period.hour': _sk_en('Hodina', 'Hour'),
    'history.period.day': _sk_en('Deň', 'Day'),
    'history.period.week': _sk_en('Týždeň', 'Week'),
    'history.period.month': _sk_en('Mesiac', 'Month'),
    'history.period.year': _sk_en('Rok', 'Year'),

    # POZN: tu bolo 14 klucov 'settings.dojo_*' - nadpis, popis, krajne
    # popisky posuvnika a pasma zivej spatnej vazby ("Vypnuté/Jemné/
    # Stredné/Výrazné/Plné" + hlasky o citatelnosti) pre panel "Pozadie
    # dojo". Panel aj fotopas nad titulkovou listou boli odstranene, takze
    # tieto kluce uz nic nevolalo - ostali by len ako 14 dalsich retazcov
    # na dopreklad do 7 jazykov v preklad_TODO.csv.
    'history.sessions_title': _sk_en('Relácie', 'Sessions'),
    'history.col_date': _sk_en('Dátum', 'Date'),
    'history.col_duration': _sk_en('Dĺžka', 'Length'),
    'history.col_avg': _sk_en('Priemer', 'Average'),
    'history.col_minmax': _sk_en('Min / max', 'Min / max'),
    'history.col_over': _sk_en('Nad hranicou', 'Over limit'),
    'history.col_triggers': _sk_en('Hlášky', 'Cues'),
    'history.col_peak': _sk_en('Špička záťaže', 'Peak load'),
    'history.col_hrr': _sk_en('HRR', 'HRR'),
    'history.col_hrpi': _sk_en('HRPI', 'HRPI'),
    'history.info_more': _sk_en('ⓘ čo to znamená', 'ⓘ what it means'),
    'history.info_less': _sk_en('ⓘ skryť', 'ⓘ hide'),
    # „Ako to vzniklo“ (0.2, slová autora) - panel v Historii aj koniec karty
    # „Plť cez rieku“ v Sprievodcovi. Nahradil dlhý zoznam štúdií: žiadna z
    # nich netestuje Zanshin ani jeho hlášky, celý zoznam je v ZDROJE.md.
    # Pod textom idú tri príklady (guide_content.PHILOSOPHY_SOURCES).
    # „Postavil som ho“ hovorí AUTOR, nie appka - preto mužský rod.
    'origin.title': _sk_en('Ako to vzniklo', 'How it came about'),
    'origin.text': _sk_en(
        'Vyrástol som s hrami ako mnohí z mojej generácie. Za očami sa v nás deje viac, než vidno. Zanshin je môj pokus skúsiť to v mieri: niečo, čo si všimne, nič nechce a nič nepredáva.\n\nZanshin nevymyslel nič nové. Stojí na verejnom výskume o tepe, strese a dýchaní a na nástrojoch, ktoré iní nechali otvorené. Postavil som ho pomocou AI a ladil na vlastných večeroch pri hraní. Je to alfa a stále sa testuje — aj preto sa ťa appka po relácii pýta, či hláška sadla, a na začiatku asi každá štvrtá, neskôr každá desiata hláška zámerne mlčí, aby sa dalo porovnať, či hlášky naozaj pomáhajú. Záťaž je priznaná zloženina troch vecí, ktoré sa z tepu naozaj dajú zistiť: o koľko si nad svojím pokojom, ako rýchlo tep stúpa a ako dlho ostáva hore. Hranice si appka po prvých pár večeroch počíta z tvojich vlastných relácií. Nie je to zdravotnícka pomôcka a nikto ju klinicky neoveroval.',
        "I grew up with games, like a lot of my generation. More goes on behind the eyes than anyone sees. Zanshin is my attempt to try it in peace: something that notices, wants nothing and sells nothing.\n\nZanshin didn't invent anything new. It stands on public research into heart rate, stress and breathing, and on tools that others left open. I built it with the help of AI and tuned it over my own evenings of gaming. It's an alpha and still being tested — that's also why the app asks you after a session whether the cue landed, and why at first roughly one cue in four, later one in ten, stays silent on purpose, so it can be compared whether the cues really help. Load is an openly admitted mix of three things that heart rate can really tell: how far you are above your own calm, how fast your pulse is climbing and how long it stays up. After the first few evenings, the app works out its thresholds from your own sessions. It is not a medical device, and nobody has validated it clinically."),
    'origin.examples': _sk_en('Pár príkladov, o ktoré sa opiera:',
                              'A few examples it leans on:'),
    'origin.full_list': _sk_en('Celý zoznam zdrojov je na GitHube v ZDROJE.md.',
                               'The full list of sources is on GitHub in ZDROJE.md.'),

    # --- metriky: kratky text (veta pri cisle) + "co to znamena" (2-3 vety) ---
    'metric.bpm.title': _sk_en('Tep teraz', 'Heart rate now'),
    'metric.bpm.short': _sk_en('Koľko úderov za minútu ti bije srdce práve teraz.',
                               'How many times per minute your heart is beating right now.'),
    'metric.bpm.more': _sk_en(
        'Základná hodnota. Sama o sebe nič nehovorí — dôležité je, ako sa mení oproti tvojmu pokoju a ako rýchlo klesá, keď sa upokojíš.',
        'The base number. On its own it says little — what matters is how it moves against your resting level and how fast it drops when you calm down.'),
    # Jednoslovny popisok karty na stranke Dnes. Karta ukazuje VELKE
    # cislo a pod nim tento popisok - `title` by tam bol privelmi
    # dlhy a v nemcine, francuzstine a rustine by rozsiril cely pravy
    # stlpec na ukor stredu (odmerane: az o 105 px).
    'metric.baseline.tag': _sk_en('pokoj', 'resting'),
    'metric.hrr.tag': _sk_en('zotavenie', 'recovery'),
    'metric.over.tag': _sk_en('nad hranicou', 'over limit'),
    'metric.breath.tag': _sk_en('hlášky', 'cues'),
    'metric.avg.tag': _sk_en('priemer', 'average'),
    'metric.max.tag': _sk_en('maximum', 'highest'),
    'metric.peak.tag': _sk_en('špička záťaže', 'peak load'),
    'metric.week.tag': _sk_en('týždeň', 'this week'),
    # 0.2 (widgets-history). Ziadna karta nesmie byt sirsia nez "nad
    # hranicou" s 12:34 (odmerane: 195 px pri 150 %) - inak rozsiri stlpec
    # na ukor stredu. Preto "cítené/merané" bez medzier (194, s " · " 200).
    'metric.session_len.tag': _sk_en('relácia', 'session'),
    'metric.last_cue.tag': _sk_en('od hlášky', 'since cue'),
    'metric.calm_time.tag': _sk_en('v pokoji', 'in calm'),
    'metric.signal.tag': _sk_en('signál', 'signal'),
    'metric.felt_vs_measured.tag': _sk_en('cítené/merané', 'felt/measured'),
    'metric.baseline.title': _sk_en('Pokojová základňa', 'Resting baseline'),
    'metric.baseline.short': _sk_en('Tvoj tep, keď ťa hra nikam netlačí.',
                                    'Your heart rate when the game is not pushing you.'),
    'metric.baseline.more': _sk_en(
        'Appka si ju počíta z tvojich najpokojnejších chvíľ. Keď stúpa deň za dňom, telo môže byť unavené alebo v strese — nie nutne z hrania (spánok, kofeín, choroba). Preto ju sledujeme v čase, nie jedno číslo.',
        'The app derives it from your calmest moments. When it climbs day after day, your body may be tired or stressed — not necessarily from gaming (sleep, caffeine, illness). That is why we track it over time, not as a single number.'),
    'metric.load.title': _sk_en('Záťaž', 'Load'),
    # C2 (0.2): stara veta "ako velmi ta hra zatazuje" slubovala viac, nez
    # appka vie - pokoj sa berie aj z predoslych vecerov, takze pruh ukaze
    # aj kavu ci unavu, nielen hru. Slovo nad pruhom je od 0.2 tep voci
    # pokoju (HeartStats.zone), nie zataz, a hlasku nespusta. Od 0.2
    # (stress-gate) ju ale v kritickom pasme zastavi - veta to hovori.
    'metric.load.short': _sk_en('Ako ďaleko je tvoj tep nad tvojím pokojom, ako rýchlo stúpa a ako dlho tam drží — z tepu, nie z HRV.',
                                'How far your pulse is above your calm, how fast it climbs and how long it stays there — from heart rate, not HRV.'),
    'metric.load.more': _sk_en(
        'Pruh záťaže sa skladá z troch vecí, ktoré sa z tepu naozaj dajú zistiť: o koľko si nad pokojom, ako rýchlo tep stúpa a ako dlho ostáva hore. Pokoj si appka berie z tvojich pokojnejších večerov, nielen z dnešného — keď dnes začínaš vyššie (káva, teplo, únava), pruh ukáže aj to, nielen hru. Slovo nad pruhom hovorí len o tom, kde je tvoj tep práve teraz: „Zvýšená“ je od 10 BPM nad pokojom, „Vysoká“ od 25 BPM a „Špička“ od tvojej hranice vysokého tepu. Kým appka nemá dosť tvojich relácií, pokoj berie len z dnešného večera a hranicu pre priemerného hráča. Hlášku slovo nespúšťa: keď záťaž prejde prah zo stránky Spúšťače, appka najprv počíta, či tam chvíľu vydrží, a až potom čaká na pauzu v hre, v ktorej už záťaž nestúpa. Kým slovo ukazuje „Špička“, appka mlčí. Nie je to HRV ani diagnóza.',
        'The load bar combines three things heart rate can actually tell: how far above your calm you are, how fast it is climbing, and how long it stays up. Your calm is taken from your calmer evenings, not just tonight — if you start higher today (coffee, heat, fatigue), the bar shows that too, not only the game. The word above the bar is only about where your pulse is right now: “Raised” starts 10 BPM above your calm, “High” at 25 BPM, and “Peak” at your high heart-rate limit. Until the app has enough of your sessions, it takes your calm from tonight only and uses a limit for an average player. The word does not trigger the cue: when the load crosses the threshold on the Triggers page, the app first counts whether it holds there for a while, and only then waits for a pause in the game in which the load is no longer climbing. While the word says “Peak”, the app stays quiet. It is not HRV and not a diagnosis.'),
    'metric.hrr.title': _sk_en('Zotavenie tepu (HRR)', 'Heart rate recovery (HRR)'),
    'metric.hrr.short': _sk_en('O koľko ti klesol tep za minútu po tom, čo vyskočil.',
                               'How much your heart rate dropped in the minute after it spiked.'),
    'metric.hrr.more': _sk_en(
        'Hrubý obraz toho, ako rýchlo sa po vypätí vraciaš dole. Väčší pokles = rýchlejšie späť k pokoju. Počíta sa z bežných herných špičiek, nie zo záťažového testu — ber ho ako svoj vlastný trend v čase, nie ako známku kondície.',
        'A rough picture of how fast you come back down after a tense moment. A bigger drop = back to calm sooner. It is read from ordinary gaming spikes, not a fitness test — treat it as your own trend over time, not a fitness score.'),
    'metric.zones.title': _sk_en('Čas nad hranicou / v pásmach', 'Time over limit / in zones'),
    'metric.zones.short': _sk_en('Koľko z relácie si strávil s vysokým tepom.',
                                 'How much of the session you spent with a high heart rate.'),
    'metric.zones.more': _sk_en(
        'Krátke špičky po headshote sú normálne. Dlhý čas nad hranicou môže znamenať, že ťa hra drží v napätí.',
        'Short spikes after a headshot are normal. A long time over the limit can mean the game keeps you tense.'),
    'metric.hrpi.title': _sk_en('HRPI', 'HRPI'),
    'metric.hrpi.short': _sk_en('Jedno číslo, ktoré spája, ako vysoko a ako dlho ti bil tep.',
                                'One number that ties together how high and how long your heart rate ran.'),
    'metric.hrpi.more': _sk_en(
        'Číslo k znamená, že tvoj tep bol aspoň k úderov za minútu po dobu aspoň k sekúnd. Spája výšku aj trvanie, takže dve relácie porovnáš jedným pohľadom.',
        'A value k means your heart rate was at least k beats per minute for at least k seconds. It joins height and duration, so you can compare two sessions at a glance.'),
    'metric.zones.calm': _sk_en('pokoj', 'calm'),
    'metric.zones.raised': _sk_en('zvýšená', 'raised'),
    'metric.zones.high': _sk_en('vysoká', 'high'),
    'metric.zones.critical': _sk_en('špička', 'peak'),

    # --- vybratelne statistiky na Dnes (2x2 mriezka, "Sumi noc" redizajn) ---
    'dashboard.stats_title': _sk_en('Moje štatistiky', 'My stats'),
    'dashboard.edit_stats': _sk_en('✎ upraviť', '✎ edit'),
    'dashboard.picker_title': _sk_en('Čo chceš vidieť', 'What you want to see'),
    # tichy riadok na spodku vyberu: strop kariet + ako menit poradie
    'dashboard.picker_hint': _sk_en(
        'Na Dnes sa zmestia 4 karty. Poradie zmeníš potiahnutím karty na inú — vymenia si miesto.',
        'Today has room for 4 cards. Drag a card onto another to swap their places.'),
    # kratky nazov pre kartu na Dnes (metric.zones.title je dlhsi, pre
    # rozbalitelnu vedu v Historii - obsah vysvetlenia (.short/.more) je
    # spolocny, len tento titulok je vlastny)
    'metric.over.more': _sk_en(
        'Koľko času tvoj tep strávil nad hranicou vysokého tepu. Tú nenastavuješ — appka si ju počíta z tvojich relácií a pomaly ju dolaďuje (vidíš ju na stránke „V hre“ v karte „Hodinky a tep“). Nie je to známka — krátke špičky patria k hre. Zaujímavé je to, keď číslo večer čo večer rastie pri rovnako dlhom hraní — vtedy sa skús pozrieť, čo sa v tie večery zmenilo.',
        'How long your heart rate stayed above your high heart-rate limit. You do not set it — the app computes it from your sessions and slowly fine-tunes it (you can see it on the “In-game” page, in the “Watch and heart rate” card). It is not a grade — short spikes are part of playing. It matters when the number grows evening after evening at the same playtime — then see whether something changed on those evenings.'),
    'metric.over.title': _sk_en('Čas nad hranicou', 'Time over the limit'),
    # Kluc 'breath' je historicky (z cias jedneho dychoveho slotu). Pocita
    # VSETKY automaticke hlasky - styri kategorie z measure.CATEGORIES sa
    # striedaju (app._dalsi_cue_slot) - preto text nesmie hovorit o dychani.
    'metric.breath.title': _sk_en('Hlášky od appky', 'Cues from the app'),
    'metric.breath.short': _sk_en(
        'Koľko hlášok ti appka v tejto relácii poslala sama — keď ti záťaž chvíľu držala hore.',
        'How many cues the app gave you on its own this session — when your load held up for a while.'),
    'metric.breath.more': _sk_en(
        'Hláška je jedna zo štyroch — ťažisko, čeľusť, uvoľnenie alebo dych — a appka strieda tie, ktoré máš zapnuté. Počíta sa len to, čo poslala sama, keď ti záťaž chvíľu držala hore; tvoje skúšanie tlačidlom „Test“ sa nezaráta. Patria sem aj hlášky, ktoré prišli len ako vizuál, bez zvuku.',
        'A cue is one of four — grounding, jaw, release or breath — and the app rotates through the ones you have switched on. Only the ones it gave on its own, when your load held up for a while, count; your own tries with the “Test” button do not. Cues that came as just the visual, without sound, count too.'),
    'metric.avg.title': _sk_en('Priemerný tep dnes', 'Average heart rate today'),
    'metric.avg.short': _sk_en(
        'Priemer tepu za celú dnešnú reláciu.',
        "Your average heart rate across today's whole session."),
    'metric.avg.more': _sk_en(
        'Jedno číslo za celú reláciu — na porovnanie deň za dňom je užitočnejšia pokojová základňa, tá počíta len tvoje najpokojnejšie chvíle.',
        'One number for the whole session — for day-to-day comparison the resting baseline is more useful, since it only counts your calmest moments.'),
    'metric.max.title': _sk_en('Najvyšší tep', 'Highest heart rate'),
    'metric.max.short': _sk_en(
        'Najvyšší tep, ktorý appka dnes zachytila.',
        "The highest heart rate the app has recorded today."),
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
    'metric.week.short': _sk_en(
        'Koľko relácií si mal tento týždeň v tomto svete a koľko to bolo spolu času.',
        'How many sessions you had this week in this world and how much time that was in total.'),
    'metric.week.more': _sk_en(
        'Týždeň sa počíta od pondelka a rátajú sa len relácie sveta, v ktorom práve si (Hra alebo Práca). Slúži len na prehľad, koľko toho appka tento týždeň zaznamenala.',
        'The week counts from Monday, and only sessions of the world you are in (Play or Work) count. It is just an overview of how much the app has logged this week.'),
    # --- 0.2 (widgets-history): pat novych kariet. Kazda hovori, co meria
    # aj co NEmeria; ziadne skore, znamka ani seria. Tie iste texty ukazuje
    # Historia (pod grafom dlzka, pokoj a signal; citene/merane pod
    # tabulkou), preto `short` nehovori len o zivej karte.
    'metric.session_len.title': _sk_en('Dĺžka relácie', 'Session length'),
    'metric.session_len.short': _sk_en(
        'Ako dlho relácia trvá — odkedy appka začala počúvať.',
        'How long the session runs — since the app started listening.'),
    'metric.session_len.more': _sk_en(
        'Relácia začína, keď appka začne počúvať, nie keď spustíš hru, a končí, keď počúvať prestane. Sú to len hodiny, nie hodnotenie: dlhá relácia nie je zlá a krátka nie je dobrá. Keď appka práve nepočúva, karta ukáže „—“.',
        'A session starts when the app starts listening, not when you launch the game, and ends when it stops listening. It is just a clock, not a rating: a long session is not bad and a short one is not good. When the app is not listening right now, the card shows “—”.'),
    'metric.last_cue.title': _sk_en('Od poslednej hlášky', 'Since the last cue'),
    'metric.last_cue.short': _sk_en(
        'Koľko minút prešlo od poslednej hlášky, ktorú ti appka v tejto relácii poslala sama.',
        'How many minutes have passed since the last cue the app gave you on its own this session.'),
    'metric.last_cue.more': _sk_en(
        'Počíta sa len hláška, ktorú appka poslala sama a naozaj sa ukázala — tvoje skúšanie tlačidlom „Test“ sa nezaráta. Kým v tejto relácii žiadna neprišla, karta ukáže „—“. Nie je to cieľ ani séria: dlhé ticho neznamená, že sa ti darí, a hláška neznamená, že robíš niečo zle. Je to len to, kedy sa appka ozvala naposledy.',
        'Only a cue the app gave on its own and that actually showed counts — your own tries with the “Test” button do not. Until one comes this session, the card shows “—”. It is not a goal or a streak: a long silence does not mean you are doing well, and a cue does not mean you are doing something wrong. It is just when the app last spoke up.'),
    'metric.calm_time.title': _sk_en('Čas v pokoji', 'Time in calm'),
    'metric.calm_time.short': _sk_en(
        'Koľko minút relácie bol tvoj tep v pásme pokoja.',
        'How many minutes of the session your pulse spent in the calm zone.'),
    'metric.calm_time.more': _sk_en(
        'Pokoj je to isté pásmo ako v paneli „Kde si dnes bol“: tep menej ako 10 BPM nad tvojím pokojom. Hovorí o tepe, nie o tom, ako pokojne si sa cítil. Nie je to skóre — viac minút neznamená lepší večer; napätý zápas tep zdvihne a tak to má byť. Na prvom večeri, kým appka tvoj pokoj ešte nepozná, karta ukáže „—“.',
        'Calm is the same zone as in the “Where the session went” panel: a pulse less than 10 BPM above your calm. It is about your heart rate, not about how calm you felt. It is not a score — more minutes do not mean a better evening; a tense match raises your pulse, and that is how it should be. On your first evening, until the app knows your calm, the card shows “—”.'),
    'metric.signal.title': _sk_en('Kvalita signálu', 'Signal quality'),
    'metric.signal.short': _sk_en(
        'Ako dobre ťa appka počuje: akú časť relácie jej naozaj chodil tep.',
        'How well the app hears you: what share of the session your heart rate actually came through.'),
    'metric.signal.more': _sk_en(
        'Percento je čas, keď tep naozaj chodil, z času od prvej vzorky. Číslo za „·“ na karte je, koľkokrát v tejto relácii tep vypadol — keď ani raz, nie je tam. Percento sa na karte ukáže až po minúte, skôr by jedna medzera vyzerala ako zlé spojenie. Hovorí o ceste hodinky → telefón → Wi‑Fi → počítač, nie o tvojom srdci ani o tebe. Keď je nízke, hlášok môže byť menej: keď tep vypadne uprostred počítania, appka začne počítať odznova. V Histórii sa ráta z celej relácie aj s čakaním, kým sa hodinky pripojili, preto tam krátke relácie vychádzajú nižšie.',
        'The percentage is the time your heart rate actually came through, out of the time since the first sample. The number after “·” on the card is how many times it dropped out this session — if it never did, it is not there. The card shows the percentage only after a minute; sooner, a single gap would look like a bad connection. It is about the path watch → phone → Wi‑Fi → PC, not about your heart or about you. When it is low, there may be fewer cues: when your heart rate drops out in the middle of counting, the app starts counting again. In History it is computed over the whole session, including the wait for the watch to connect, so short sessions come out lower there.'),
    'metric.felt_vs_measured.title': _sk_en('Cítené a merané', 'Felt and measured'),
    'metric.felt_vs_measured.short': _sk_en(
        'Tvoja vnímaná záťaž z dotazníka vedľa nameranej špičky záťaže, obe 0–10.',
        'Your felt load from the questionnaire next to the measured peak load, both 0–10.'),
    'metric.felt_vs_measured.more': _sk_en(
        'Karta na Dnes berie poslednú ukončenú reláciu tohto sveta (Hra alebo Práca), detail v Histórii tú, ktorú si vybral. Prvé číslo je, ako si záťaž ohodnotil v dotazníku po relácii. Druhé je najvyššia záťaž tej istej relácie (špička 0–100) vydelená desiatimi. Nemusia sa zhodovať a ani jedno nie je „to správne“ — tep nevidí, ako ti bolo, a ty necítiš každý úder. Rozdiel medzi nimi nie je chyba, je to informácia. Keď si dotazník preskočil, ukáže „—“.',
        'The card on the Today page takes your last finished session in this world (Play or Work); the detail in History takes the one you picked. The first number is how you rated the load in the questionnaire after the session. The second is the highest load of that same session (the 0–100 peak) divided by ten. They do not have to match, and neither is “the right one” — your pulse cannot see how it felt, and you do not feel every beat. A gap between them is not an error, it is information. If you skipped the questionnaire, it shows “—”.'),
    'dashboard.unit.baseline': _sk_en('BPM', 'BPM'),
    'dashboard.unit.hrr': _sk_en('BPM za minútu', 'BPM per minute'),
    'dashboard.unit.over': _sk_en('za dnešnú reláciu', "this session"),
    'dashboard.unit.breath': _sk_en('automaticky', 'automatic'),
    'dashboard.unit.avg': _sk_en('za reláciu', 'this session'),
    'dashboard.unit.max': _sk_en('za reláciu', 'this session'),
    'dashboard.unit.peak': _sk_en('z 0–100', 'of 0-100'),
    'dashboard.unit.session_len': _sk_en('od začiatku relácie', 'since the session began'),
    'dashboard.unit.last_cue': _sk_en('od poslednej hlášky', 'since the last cue'),
    'dashboard.unit.calm_time': _sk_en('v pokoji za reláciu', 'in calm this session'),
    'dashboard.unit.signal': _sk_en('času s tepom', 'of the time with a pulse'),
    'dashboard.unit.felt_vs_measured': _sk_en('cítené · merané, 0–10', 'felt · measured, 0–10'),
    # Tvar cisla na kartach a v detaile relacie - ako kluc, aby ho jazykova
    # faza vedela prelozit (napr. 分). {m} prichadza uz ako dve cifry.
    'dashboard.fmt.min': _sk_en('{n} min', '{n} min'),
    'dashboard.fmt.h_min': _sk_en('{h} h {m} min', '{h} h {m} min'),
    'dashboard.fmt.pct': _sk_en('{n} %', '{n}%'),

    # --- odporucania z analyzy na pozadi (postrehy, nie diagnozy) ---
    # Odporucania o TICHU. Jedine, ktore hracovi hovoria, co ma urobit -
    # preto stoja na cislach zo spustaca, nie na dojme z tepu.
    # {n} = priemer za posledné večery (`hr_insights`), nie súčet. Rada je
    # tá istá ako v `session.end.none_dropouts` — jedna pravdivá reťaz.
    'insight.cue_dropouts': _sk_en('Tep ti za posledné večery vypadával priemerne {n}× za večer práve počas počítania a počítanie sa zakaždým začalo odznova — preto môže byť hlášok menej. Tep ide z hodiniek do telefónu cez Bluetooth a z telefónu cez Wi‑Fi do počítača — maj hodinky pri telefóne a telefón blízko Wi‑Fi routra. Keď odchádzaš od počítača, vezmi telefón so sebou.',
                                    'Over the last evenings your heart rate dropped out {n}× per evening on average while I was counting, and each time the count started over — so there may be fewer cues. It goes from the watch to the phone over Bluetooth, and from the phone to the PC over Wi‑Fi — keep the watch near the phone and the phone near the Wi‑Fi router. When you step away from the PC, take the phone with you.'),
    'insight.cue_never_above': _sk_en('Posledné {n} večery sa záťaž ani raz nedostala nad hranicu — takže sa appka nemala prečo ozvať. Hranica nie je nastavenie — appka si ju počíta z tvojich relácií a posúva ju, ako ťa spoznáva. Aktuálnu vidíš v Nastaveniach → Spúšťače.',
                                       'Over the last {n} evenings your load never crossed the threshold, so the app had no reason to speak. The threshold is not a setting — the app computes it from your sessions and moves it as it gets to know you. You can see the current one in Settings → Triggers.'),
    'insight.cue_almost': _sk_en('Záťaž hore bola, ale najdlhšie {sec} s v kuse — chýbalo do {need} s. Bolo to tesne. Appka zámerne čaká, kým záťaž vydrží hore, aby sa neozývala pri každej krátkej špičke.',
                                  'Your load did rise, but the longest stretch was {sec} s — short of {need} s. It was close. The app waits on purpose for the load to hold, so it does not speak up at every short spike.'),
    'insight.cue_far': _sk_en('Záťaž sa nad hranicu dostala, ale len na chvíľu — najdlhšie {sec} s z potrebných {need} s. Tvoje telo ide hore a dole rýchlejšie, než appka čaká. Na krátke špičky sa appka zámerne neozýva — nastavovať tu nie je čo.',
                               'Your load did cross the threshold, but only briefly — the longest stretch was {sec} s out of {need} s. Your body rises and falls faster than the app waits for. The app stays quiet on short spikes on purpose — there is nothing to set here.'),
    'insight.need_more': _sk_en(
        'Zatiaľ {n} z {need} relácií — po troch začne appka hľadať vzory naprieč nimi.',
        '{n} of {need} sessions so far — after three the app starts looking for patterns across them.'),
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
        'V reláciách od 1,5 h prišlo {share} % hlášok v prvej hodine. Ak sa to opakuje, možno ťa rozbieha práve začiatok — skús pokojnejší rozjazd a sleduj, či sa to zmení.',
        "In sessions of 1.5 h or longer, {share} % of the app's cues came in the first hour. If that keeps happening, the start of a session may be what winds you up — try a calmer warm-up and see if it changes."),
    'insight.triggers_late': _sk_en(
        'V reláciách od 2,5 h prišlo {share} % hlášok až po dvoch hodinách — dlhé relácie ťa môžu držať v napätí; skús kratšie relácie s prestávkou.',
        "In sessions of 2.5 h or longer, {share} % of the app's cues came after the first two hours — long sessions may keep you tense; try shorter sessions with a break."),
    'insight.over_up': _sk_en(
        'V posledných reláciách si strávil nad hranicou väčšiu časť relácie než predtým (priemer {minutes} min). Môže za tým byť hra, ale aj spánok či kofeín — alebo len to, že si appka hranicu po každej relácii dolaďuje podľa tvojich dát. Ak to tak ostane, môžeš skúsiť dýchanie zo Sprievodcu.',
        'You have spent a bigger share of your sessions over the limit recently than before (average {minutes} min). It could be the game — or sleep or caffeine — or simply that the app fine-tunes your limit from your own data after each session. If it stays that way, you could try the breathing from the Guide.'),
    'insight.steady': _sk_en(
        'V {n} reláciách si appka zatiaľ nič nevšimla.',
        "The app hasn't noticed anything across {n} sessions so far."),

    # --- tri zdroje v appke (guide_content.PHILOSOPHY_SOURCES) ---
    # 0.2: popisky su autorove priklady pod textom „Ako to vzniklo“, nie nazvy
    # studii. Ostatne zdroje (source1-9, 13-17) z appky odisli do ZDROJE.md.
    'guide.philosophy.source12': _sk_en(
        'pri výdychu sa tep prirodzene spomalí (Lehrer & Gevirtz, 2014)',
        'your heart naturally slows as you breathe out (Lehrer & Gevirtz, 2014)'),
    'guide.philosophy.source11': _sk_en(
        'pomalé dýchanie sa spája s pokojnejším stavom (Zaccaro a kol., 2018)',
        'slow breathing goes together with a calmer state (Zaccaro et al., 2018)'),
    'guide.philosophy.source10': _sk_en(
        'súťažné hranie spúšťa skutočnú stresovú reakciu srdca (Ketelhut & Nigg, 2024)',
        'competitive play triggers a real stress response in the heart (Ketelhut & Nigg, 2024)'),

    # --- onboarding krok 3: druhy dovod pre hodinky (historia) ---
    'ob.step3.body2': _sk_en(
        'A ešte: appka si pamätá každú reláciu. Po pár týždňoch hrania ti začne ukazovať tvoje vlastné trendy — napríklad ako rýchlo sa po vypätí upokojuješ — čierne na bielom, nie pocitovo.',
        'And one more thing: the app remembers every session. After a few weeks of play it starts showing your own trends — like how fast you settle after a tense moment — in plain numbers, not by feel.'),

    # --- parovanie: viac adries ---
    'hr.pair_other_ips': _sk_en(
        'Ďalšie adresy tohto PC (ak hodinky prvú nevidia, skús tieto — každá je iná sieť/adaptér): {ips}',
        'Other addresses of this PC (if the watch cannot reach the first one, try these — each is a different network/adapter): {ips}'),
    'hr.pair_ip_note': _sk_en(
        'Toto je adresa počítača v tvojej sieti. V nastaveniach nechaj 0.0.0.0 — appka počúva na všetkých sieťach naraz, toto číslo sa píše len do telefónu.',
        'This is your PC’s address on your network. Keep 0.0.0.0 in settings — the app listens on every network at once; this number only goes into the phone.'),
    'dnes.stat_hrr': _sk_en('Zotavenie tepu (HRR)', 'Heart rate recovery (HRR)'),
    'dnes.stat_hrpi': _sk_en('HRPI', 'HRPI'),
    'history.sessions_count': _sk_en('{n} relácií', '{n} sessions'),
    'history.minutes': _sk_en('{m} min', '{m} min'),
})


# --- UX feedback z live testu: jednotny priatelsky ton (tykanie), kratsie
# parovanie, nove menu (Nastavenia ako skupina), dock. Prepisy PREPISUJU
# starsie formalne znenia vyssie (STRINGS.update) - sk/en rucne, ostatnych 7
# jazykov zatial anglicky (preklad_TODO.csv). Stale vecne a jasne, len ludske.
STRINGS.update({
    # --- navigacia: 3 hlavne polozky, zvysok su karty v Nastaveniach ---
    'nav.nastavenia_tabs.spustace': _sk_en('Spúšťače', 'Triggers'),
    'nav.nastavenia_tabs.zvuk': _sk_en('Zvuk', 'Sound'),
    'nav.nastavenia_tabs.vhre': _sk_en('V hre', 'In game'),
    'nav.nastavenia_tabs.guide': _sk_en('Sprievodca', 'Guide'),
    'nav.nastavenia_tabs.vseobecne': _sk_en('Všeobecné', 'General'),
    # POZN: 'dock.mute_tip', 'dock.unmute_tip', 'dock.snooze_tip' a
    # 'dock.profile_tip' odisli s rychlym dokom (viz app.py, `_build_ui`).
    # Tieto dva zostali - nesie ich bodka stavu v rade a kontrolka tepu.
    # 24. 9.: text nesie cas konca, nie zvysne minuty - nastavi sa raz a
    # "zostava 30 min" by o chvilu klamalo. O merani nic: skratka ide aj
    # ked appka nepocuva, a vtedy by "merám ďalej" klamalo.
    'dock.snooze_active_tip': _sk_en('Teraz nie — do {until} sa neozvem',
                                     "Not now — I won't speak up until {until}"),
    'dock.pulse_live_tip': _sk_en('Tep z hodiniek beží', 'Heart rate is live'),
    'dock.start': _sk_en('▶  Spustiť', '▶  Start'),
    'dock.stop': _sk_en('■  Zastaviť', '■  Stop'),
    'dock.start_tip': {
        'sk': 'Spusti počúvanie tepu — appka sa začne ozývať',
        'en': 'Start listening to your heart rate — the app will start speaking up',
        'ja': '心拍の受信を開始 — アプリが声をかけ始めます',
        'zh': '开始接收心率——应用会开始出声',
        'ru': 'Начать слушать пульс — приложение начнёт подавать голос',
        'es': 'Empezar a escuchar el pulso: la app empezará a hablar',
        'de': 'Puls-Empfang starten — die App beginnt sich zu melden',
        'fr': 'Commencer à écouter le pouls — l’app va se manifester',
        'pt': 'Começar a ouvir o pulso — o app vai começar a falar',
    },
    'dock.stop_tip': _sk_en('Zastav počúvanie — nič sa nespustí, kým to znova nezapneš',
                            'Stop listening — nothing fires until you start again'),
    # Tlačidlo 😴 už neštíši natvrdo na 20 minút — otvára výber dĺžky.
    'dnes.empty_title': _sk_en('Tu uvidíš svoj tep', 'Your heart rate shows up here'),
    'dnes.empty_body': _sk_en(
        'Keď spáruješ hodinky, appka ti sem kreslí tep a záťaž — a keď ti záťaž chvíľu drží hore, sama sa ozve hláškou.',
        'Once you pair your watch, the app draws your heart rate and load here — and when your load holds up for a while, it gives you a cue on its own.'),
    'dnes.empty_btn': _sk_en('Spárovať hodinky', 'Pair your watch'),

    # --- Zvuk a hlas: bez skratiek (TTS, SFX, SAPI5) v popiskoch ---
    'settings.title': _sk_en('Zvuk a hlas', 'Sound and voice'),
    'settings.cooldown': _sk_en('Pauza medzi pripomienkami:', 'Pause between reminders:'),
    'settings.volume': _sk_en('Hlasitosť:', 'Volume:'),
    'settings.balance': _sk_en('Pomer zvuk ↔ hlas:', 'Sound ↔ voice mix:'),
    'settings.balance_center': _sk_en('napoly', 'even'),
    'settings.balance_sfx': _sk_en('zvuk', 'sound'),
    'settings.balance_tts': _sk_en('hlas', 'voice'),
    'settings.overlap': _sk_en('Hlášky sa môžu prekrývať', 'Voice lines may overlap'),
    'settings.engine': _sk_en('Hlas generuje:', 'Voice comes from:'),
    'settings.voice': _sk_en('Hlas:', 'Voice:'),
    'settings.rate': _sk_en('Rýchlosť reči:', 'Speech speed:'),
    'engine.edge': _sk_en('Prirodzený hlas (Edge, potrebuje internet na prípravu)',
                          'Natural voice (Edge, needs internet to prepare)'),
    'engine.sapi': _sk_en('Hlas z Windows (funguje aj bez internetu)',
                          'Windows voice (works offline)'),
    'mode.tts': _sk_en('Hlas', 'Voice'),
    'mode.sfx': _sk_en('Zvuk', 'Sound'),
    'mode.combo': _sk_en('Hlas + zvuk', 'Voice + sound'),
    'settings.strict_global_lock': _sk_en('Naraz len jedna pripomienka', 'One reminder at a time'),

    # --- Spustace ---
    # FAZA 3: klaves uz nic nespusta, takze povodny text ("viac spustacov
    # moze mat rovnaky klaves") by klamal. Prekreslenie celej stranky je
    # faza 5; toto je minimum, aby appka nehovorila nepravdu.
    'slots.title': _sk_en('Čo appka hovorí', 'What the app says'),
    # 0.2 (stress-gate): to isté načasovanie ako `tour.triggers.body`.
    'slots.hint': _sk_en(
        'Kedy sa ozve, rozhoduje tvoje telo — appka čaká, kým ti záťaž chvíľu drží hore, a ozve sa v prestávke, keď už záťaž nestúpa; kým je tep v pásme Špička, mlčí. Tu si nastavíš, čo presne povie. „Hlas + zvuk“ prehrá oboje.',
        'When it speaks is decided by your body — the app waits until your load stays up for a while, then speaks in a pause once the load has stopped climbing; while your pulse is in the peak zone, it stays quiet. Here you set what it actually says. “Voice + sound” plays both.'),
    'settings.auto_profile': _sk_en(
        'Pri známej hre sama prepnem profil a spustím počúvanie',
        'When a game I know is running, I switch the profile and start listening by myself'),
    # Presne, co prepinac robi - a ze pri vypnutom sa procesy necitaju vobec
    # (`GameProcessWatcher` vtedy nebezi). {games} = `game_profiles.known_games`.
    'settings.auto_profile_sub': _sk_en(
        'Hry, ktoré poznám: {games}. Každých pár sekúnd porovnám názvy bežiacich '
        'procesov s týmto zoznamom – z procesov nič iné nečítam. Keď hru nájdem, '
        'prepnem na jej profil (ak ho nemáš, založím ho s predvolenými hláškami) '
        'a spustím počúvanie. Keď hru zavrieš, zastavím ho, ak som ho spustila ja. '
        'Vypnuté = zoznam procesov vôbec nečítam.',
        'Games I know: {games}. Every few seconds I compare the names of running '
        'processes with this list - I read nothing else from them. When I find a '
        'game, I switch to its profile (if you have none, I create one with the '
        'default cues) and start listening. When you close the game, I stop '
        'listening, if I was the one who started it. Off = I do not read the '
        'process list at all.'),
    'settings.auto_profile_unavailable': _sk_en(
        'Automatické prepínanie podľa hry teraz nejde (chýba knižnica psutil)',
        'Automatic switching by game is unavailable right now (psutil library missing)'),

    # --- V hre ---
    'overlay.dialog_title': _sk_en('Vizuály v hre', 'Visuals in game'),
    'settings.overlay_button': _sk_en('🎮 Vizuály v hre…', '🎮 Visuals in game…'),
    'overlay.monitor.label': _sk_en('Na ktorej obrazovke kresliť', 'Which screen to draw on'),
    'hud.section_title': _sk_en('Panel s tepom v hre', 'Heart-rate panel in game'),
    'hud.enable': _sk_en('Ukázať panel v hre — pre stream',
                         'Show the panel in game — for streaming'),
    # FAZA 3: panel ostava, ale popis hovori, PRE KOHO je. Trvale zobrazeny
    # tep pocas hrania rusi - lista sa vnima periferne, ale cislo sa musi
    # citat, a to je presne ta pozornost, ktoru appka ma setrit. Divakovi na
    # streame naopak dava zmysel. Preto je vypnuty a preto to tu stoji.
    'hud.hint': _sk_en(
        'Malý panel v rohu: tvoj tep, krivka za posledné 3 minúty, záťaž a priebeh relácie. Divákom na streame dáva zmysel; tebe počas hrania skôr uberá pozornosť, preto je vypnutý. Klik cezeň prejde do hry a v Alt+Tab ho neuvidíš.',
        'A small corner panel: your heart rate, the last 3 minutes, load and session progress. It makes sense for stream viewers; while you play it mostly costs you attention, which is why it is off. Clicks pass through to the game and it never shows in Alt+Tab.'),
    # Prvych ~30 vzoriek relacie appka este nema tvoju zakladnu. Namiesto
    # zataze voci hrubemu odhadu ukaze HUD aj Dnes toto (hud_paint.render_hud).
    'hud.calibrating': _sk_en('kalibrujem…', 'calibrating…'),
    'settings.hr_section_title': _sk_en('Hodinky a tep', 'Watch and heart rate'),
    'settings.hr_enable_switch': _sk_en('Počúvať tep z hodiniek', 'Listen for heart rate from the watch'),
    'settings.hr_ip_hint': _sk_en(
        'Nechaj 0.0.0.0 (počúva všade) — nevieš čo dať? Pozri „Ako spárovať hodinky“ nižšie.',
        "Leave 0.0.0.0 (listens everywhere) — not sure? See “How to pair your watch” below."),
    'settings.hr_port_hint': _sk_en('Nechaj 4455, ak nevieš — rovnaké číslo musí byť aj v appke na hodinkách.',
                                    "Leave 4455 unless you know better — the watch app needs the same number."),

    # --- Sprievodca ---
    'guide.panel_subtitle': _sk_en(
        'Čo sa ti v tele deje pri každej pripomienke a čo s tým spraviť, keď sa appka ozve.',
        'What happens in your body at each cue and what to do about it when the app speaks up.'),
    'guide.block.physiology': _sk_en('Čo sa deje v tele', 'What happens in your body'),
    # Nie „Čo na to veda“: blok je z casti prax, z casti par citovanych studii -
    # nadpis nesmie slubovat viac, nez text pod nim dava.
    'guide.block.science': _sk_en('Prečo to môže pomôcť', 'Why it may help'),
    'guide.block.instruction': _sk_en('Čo spraviť ty', 'What you do'),
    # KNOWN_ISSUES.md #5: "nie je to zdravotnicka pomocka" uz nie len v
    # README. Jedna ticha veta, nie varovanie - ten isty ton ako
    # 'history.insights_note' („postrehy a tipy, nie diagnózy“).
    'guide.not_medical_note': _sk_en(
        'Sú to všeobecné tipy pre pohodu, nie lekárska rada — Zanshin nie je zdravotnícka pomôcka. Ak máš ťažkosti so srdcom alebo s dýchaním, najprv sa poraď s lekárom.',
        'These are general wellbeing tips, not medical advice — Zanshin is not a medical device. If you have heart or breathing problems, check with a doctor first.'),
    'settings.guide_row': _sk_en('Prečo práve čeľusť, ťažisko a dych', 'Why jaw, balance and breath'),

    # --- parovanie hodiniek: kroky ostavaju, text kratsi (bola stena textu) ---
    'hr.pair_intro': _sk_en(
        'Appka sa tvári ako OBS — telefón jej posiela tep cez appku „HeartRateOnStream for OBS“. Nastavíš raz, potom to chodí samo.',
        'The app pretends to be OBS — your phone sends heart rate through the “HeartRateOnStream for OBS” app. Set it up once, then it just runs.'),
    'hr.step1_body': _sk_en('Telefón s hodinkami aj tento počítač na tej istej Wi‑Fi (nie cez mobilné dáta).',
                            'Phone with the watch and this PC on the same Wi‑Fi (not mobile data).'),
    'hr.step2_body': _sk_en('Stiahni „HeartRateOnStream for OBS“ (Google Play / App Store) a prepoj ju s hodinkami.',
                            'Get “HeartRateOnStream for OBS” (Google Play / App Store) and connect it to your watch.'),
    'hr.step3_body': _sk_en('V appke na telefóne zadaj adresu a port z rámika hore. Heslo nechaj prázdne.',
                            'In the phone app enter the address and port from the box above. Leave the password empty.'),
    'hr.step4_body': _sk_en('Po pripojení vyber scénu „Zanshin“ a zdroj „Tep“. Ak vieš posielať aj kroky a rýchlosť, sú tam zdroje „Kroky“ a „Rychlost“.',
                            'Once connected, pick the scene “Zanshin” and the source “Tep”. If you can also send steps and speed, the sources “Kroky” and “Rychlost” are there too.'),
    'hr.step5_body': _sk_en('Vráť sa sem a zapni „Počúvať tep z hodiniek“. Tep uvidíš do pár sekúnd.',
                            'Come back here and turn on “Listen for heart rate from the watch”. You will see it within seconds.'),
    'hr.trouble_body': _sk_en(
        'Skontroluj scénu „Zanshin“ a zdroj „Tep“ v telefóne a či hodinky naozaj merajú. Pri prvom spustení Windows spýta, či appku pustiť do siete — ak si to odmietol, hodinky sa nepripoja (povoľ ju vo firewalle). Ak port obsadil iný program, zmeň ho tu aj v telefóne.',
        'Check the “Zanshin” scene and “Tep” source on the phone, and that the watch is actually measuring. On first run Windows asks whether to allow the app on the network — if you declined, the watch cannot connect (allow it in the firewall). If another program took the port, change it here and on the phone.'),
    'hr.pair_other_ips': _sk_en('Ďalšie adresy tohto PC (ak prvá nejde): {ips}',
                                'Other addresses of this PC (if the first does not work): {ips}'),
    'hr.pair_ip_note': _sk_en('V nastaveniach nechaj 0.0.0.0 — toto číslo ide len do telefónu.',
                              'Keep 0.0.0.0 in settings — this number only goes into the phone.'),
    # 0.2 skryta IP: adresa PC sa na obrazovke neukaze sama (stream,
    # screenshot) - az na klik, a len do restartu appky (netinfo.mask_ip).
    'hr.ip_show': _sk_en('Ukázať IP', 'Show IP'),
    'hr.ip_hide': _sk_en('Skryť IP', 'Hide IP'),
    'hr.ip_hidden_note': _sk_en(
        'Adresu skrývam, aby ju nebolo vidno na streame ani na screenshote. Do telefónu ju prepíšeš po kliku na „Ukázať IP“.',
        'I keep the address hidden so it does not show up on a stream or in a screenshot. Click “Show IP” to copy it into the phone.'),

    # --- dychovy cyklus nastavitelny v sekundach (Vizuály v hre -> slot Dych) ---
    'overlay.breath_seconds': _sk_en('Dychový cyklus (v sekundách)',
                                     'Breathing cycle (in seconds)'),
    'overlay.breath_inhale': _sk_en('Dĺžka nádychu (s)', 'Inhale length (s)'),
    'overlay.breath_exhale': _sk_en('Dĺžka výdychu (s)', 'Exhale length (s)'),

    # POZN: cela sekcia 'minimalisticky rezim' tu bola - 'settings.minimal_mode',
    # 'settings.minimal_mode_sub', 'minimal.expand_tip' aj
    # 'log.minimal_mode_on/off'. Celoappkovy prepinac bol odstraneny, takze
    # tieto kluce uz nic nevolalo (osirely balast, ktory sa navyse tahal do
    # preklad_TODO.csv ako 3 dalsie retazce na dopreklad do 7 jazykov).
    # Rovnaka funkcia (BPM + 4 ikonky) je teraz sucastou HUD panela v hre
    # ("Ukazat panel v hre" vo Vizualoch), nie prepnutie celeho okna appky.
    # Viz 'hud.trigger_row.*' nizsie.
    # POZN: 'hud.trigger_row.title' znelo povodne "Ukázať panel v hre" -
    # DOSLOVA to iste ako 'hud.enable' o kus vyssie na tej istej stranke.
    # Na obrazovke tak boli pod sebou tri rovnake popisky a DVA rozne
    # prepinace: jeden zapinal HUD s tepom, druhy riadok ikoniek, a nedalo
    # sa rozoznat ktory je ktory. Nazov karty preto hovori, CO to je
    # (ikonky funkcii), a prepinac zvlast, CO robi.
    'hud.trigger_row.title': _sk_en('Ikonky funkcií v hre', 'Function icons in-game'),
    'hud.trigger_row.toggle': _sk_en('Ukázať ikonky v hre', 'Show icons in-game'),
    'hud.trigger_row.sub': _sk_en(
        'Pod panelom s tepom sa ukážu piktogramy tvojich štyroch hlášok. Sú len na pohľad a vizuály v hre nenahrádzajú — hláška potrebuje aspoň jeden z nich zapnutý.',
        'Shows the icons of your four cues under the heart-rate panel. They are only for show and do not replace the in-game visuals — a cue needs at least one of those turned on.'),
    'hud.trigger_row.color': _sk_en('Farba ikoniek', 'Icon colour'),
    'hud.trigger_row.color_theme': _sk_en('Farba témy', 'Theme colour'),
    # POZN: 'hud.snooze.title' ("Stíšiť appku na…") tu bolo ako nadpis
    # riadku s ozubeným kolieskom na stránke V hre. Výber dĺžky sa presunul
    # do doku (tlačidlo 😴), kde nadpis netreba — nesie ho tooltip.
    'hud.snooze.5min': _sk_en('5 minút', '5 minutes'),
    'hud.snooze.20min': _sk_en('20 minút', '20 minutes'),
    'hud.snooze.40min': _sk_en('40 minút', '40 minutes'),
    'hud.snooze.60min': _sk_en('60 minút', '60 minutes'),
    'hud.snooze.cancel': _sk_en('Zrušiť stíšenie', 'Cancel snooze'),
    'log.hotkey_on': _sk_en('Klávesová skratka {combo} je pripravená — stíši ma na pol hodiny', 'Hotkey {combo} is ready — it will quiet me for half an hour'),
    # 24. 9.: "teraz nie" uz nie je zastavenie - spinac v pase a ikona v
    # lište zastavia aj meranie, tak to veta hovori narovinu.
    # 0.2.1: tato veta ide do dennika uz len BEZ ikony v liste (chyba
    # pystray/PIL) - s listou ide `log.hotkey_failed_tray`. Ikonu v liste
    # preto nemenuje: tam, kde sa ukaze, ziadna nie je.
    'log.hotkey_failed': _sk_en('Skratku {combo} drží iná aplikácia, takže „teraz nie“ nepôjde. Umlčať ma vieš zastavením v páse hore — tým však prestanem aj merať.', 'Another app holds {combo}, so “not now” won’t work. You can still stop me in the top bar — but then I stop measuring too.'),
    'log.snooze_started': _sk_en('Teraz nie: {minutes} minút sa neozvem. Počúvanie to nezastaví.', 'Not now: I won’t speak up for {minutes} minutes. It doesn’t stop listening.'),
    'log.snooze_ended': _sk_en('Stíšenie skončilo', 'Snooze ended'),
    'log.snooze_cancelled': _sk_en('Stíšenie zrušené', 'Snooze cancelled'),
})


# --- Grafy na stránkach Dnes a História -----------------------------------
# Stopa relácie, rozdelenie času v pásmach, odchýlka na kartách, osi a
# mriežka dní. Ton je rovnaký ako inde: čo vidíme, nie čo to o tebe hovorí.
STRINGS.update({
    'dnes.trace_title': _sk_en('Stopa relácie', 'Session trace'),
    'dnes.trace_meta': _sk_en('{time} · hlášky {n}×', '{time} · cues {n}x'),
    'dnes.zones_title': _sk_en('Kde si dnes bol', 'Where the session went'),
    'dnes.zones_hint': _sk_en(
        'Koľko z relácie si strávil v ktorom pásme. Pásma sa merajú voči tvojej '
        'vlastnej pokojovej základni, nie voči tabuľkovej hodnote.',
        'How much of the session you spent in each zone. Zones are measured '
        'against your own resting baseline, not against a chart value.'),

    # Kratko zamerne: karta je siroka asi 200 px a dlhsia veta sa v nej
    # orezala uprostred slova. Z kolkych relacii je priemer, ukazuje aj
    # mikrograf vedla cisla.
    # POZN: tu boli 'dashboard.delta_up/down/same' - veta o odchylke pod
    # cislom na karte ("▲ 3 oproti priemeru z 8"). Odisli s mikrografom;
    # dovod je v app.py pri `_dashboard_stat_value`.

    # --- stránka Zvuk (prestavaná na SettingRow) -------------------------
    # Názvy bez dvojbodky: v riadku nastavenia stojí názov nad vysvetlením,
    # nie pred poľom. Vysvetlenia sú to hlavné — pôvodná stránka bola jediná
    # v appke, ktorá pri ovládačoch nemala ani vetu.
    # Panel sa nevolá "Hlas": riadok v ňom sa volá tiež "Hlas" a nadpis
    # zhodný s položkou pod sebou sa číta ako preklep.
    'settings.audio_voice_title': _sk_en('Hovorené hlášky', 'Spoken lines'),
    'settings.audio_volume_title': _sk_en('Hlasitosť', 'Loudness'),
    'settings.audio_timing_title': _sk_en('Časovanie', 'Timing'),
    'settings.cooldown': _sk_en('Pauza medzi pripomienkami', 'Pause between reminders'),
    'settings.cooldown_sub': _sk_en(
        'Najkratší čas, ktorý musí uplynúť, kým appka prehovorí znova. '
        'Krátka pauza pripomína často, dlhá ťa nechá hrať.',
        'The shortest time before the app speaks again. A short pause reminds '
        'you often, a long one leaves you to play.'),
    'settings.volume': _sk_en('Hlasitosť', 'Volume'),
    'settings.volume_sub': _sk_en(
        'Platí len pre pripomienky. Hlasitosť hry sa tým nemení.',
        'Applies to reminders only. It does not change the game volume.'),
    'settings.balance': _sk_en('Pomer zvuk ↔ hlas', 'Sound ↔ voice mix'),
    'settings.balance_sub': _sk_en(
        'Ako sa hlasitosť rozdelí medzi zvukový efekt a hovorenú hlášku. '
        'Vľavo vedie zvuk, vpravo hlas.',
        'How the volume splits between the sound effect and the spoken line. '
        'Left favours the sound, right favours the voice.'),
    'settings.overlap': _sk_en('Hlášky sa môžu prekrývať', 'Voice lines may overlap'),
    'settings.overlap_sub': _sk_en(
        'Vypnuté: hlášky čakajú jedna na druhú. Zapnuté: môžu zaznieť naraz — '
        'hodí sa, keď máš veľa spúšťačov blízko pri sebe.',
        'Off: lines wait for each other. On: they can sound at once — useful '
        'when several triggers fire close together.'),
    'settings.engine': _sk_en('Hlas generuje', 'Voice comes from'),
    'settings.engine_sub': _sk_en(
        'Prirodzený hlas znie lepšie, ale hlášky si musí vopred pripraviť cez '
        'internet. Hlas z Windows je po ruke vždy a hneď.',
        'The natural voice sounds better but has to prepare the lines over the '
        'internet first. The Windows voice is always available right away.'),
    'settings.voice': _sk_en('Hlas', 'Voice'),
    # Pocas pocuvania appka na Microsoft nechodi (`_speak_text`): chybajuca
    # hlaska zaznie hlasom z Windows a pripravi sa az po `stop_listening`.
    'log.edge_not_cached_later': _sk_en(
        'Edge hláska ešte nie je pripravená — tentoraz hovorím hlasom z Windows. '
        'Počas hry ju nepripravujem; pripravím ju, keď zastavíš počúvanie.',
        "The Edge line isn't ready yet - speaking with the Windows voice this time. "
        "I don't prepare it during play; I'll do it when you stop listening."),
    # To iste pre celu pripravu (`pregenerate`): auto-profil pri starte hry,
    # prepnutie profilu ci zmena hlasu pocas pocuvania sa odlozia na po hre.
    'edge.after_game': _sk_en(
        'Hlášky pripravím, keď zastavíš počúvanie.',
        "I'll prepare the lines when you stop listening."),
    'settings.voice_sub': _sk_en(
        'Použije sa pre každý spúšťač, ktorý nemá nastavený vlastný hlas.',
        'Used for every trigger that has no voice of its own.'),
    'settings.rate': _sk_en('Rýchlosť reči', 'Speech speed'),
    'settings.rate_sub': _sk_en(
        'Mínus spomaľuje, plus zrýchľuje. V strese sa pomalšia reč počúva lepšie.',
        'Minus slows it down, plus speeds it up. Slower speech is easier to '
        'follow under stress.'),
    'settings.preview': _sk_en('Ako to znie', 'How it sounds'),
    'settings.preview_sub': _sk_en(
        'Prehrá prvú pripomienku presne tak, ako zaznie v hre — s týmto hlasom, '
        'hlasitosťou aj pomerom.',
        'Plays the first reminder exactly as it will sound in-game — with this '
        'voice, volume and mix.'),
    'settings.preview_btn': _sk_en('Vyskúšať', 'Try it'),
    # Slová pri posuvníkoch: "5.0 s" ani "-4" samy nepovedia, či je to veľa.
    'settings.pace_often': _sk_en('často', 'often'),
    'settings.pace_balanced': _sk_en('vyvážene', 'balanced'),
    'settings.pace_rare': _sk_en('zriedka', 'rarely'),
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
    # --- export relacii do tabulky ----------------------------------------
    'history.export_btn': _sk_en('Exportovať do tabuľky', 'Export to a spreadsheet'),
    'history.export_filetype': _sk_en('Tabuľka pre Excel (CSV)', 'Excel spreadsheet (CSV)'),
    'history.export_local': _sk_en(
        'Tep ani relácie appka nikam neposiela — sú len v tvojom počítači '
        'a súbor si uložíš, kam chceš.',
        'The app sends your heart rate and sessions nowhere — they stay on '
        'this computer, and you choose where the file goes.'),
    'history.export_empty': _sk_en('Zatiaľ nie je čo exportovať — najprv odohraj reláciu so senzorom tepu.',
                                   'Nothing to export yet — play a session with the heart rate sensor first.'),
    'history.export_extra': _sk_en('Popri tom sa uložilo:\n{files}',
                                   'Alongside it, these were saved:\n{files}'),
    'history.export_col.longest_above_s': _sk_en('najdlhšie nad hranicou (s)',
                                                 'longest stretch above (s)'),
    'history.export_col.above_runs': _sk_en('úsekov nad hranicou', 'runs above'),
    'history.export_col.cancelled_dip': _sk_en('zrušené poklesom', 'cancelled by dip'),
    'history.export_col.cancelled_gap': _sk_en('zrušené výpadkom', 'cancelled by dropout'),
    'history.export_col.hold_s': _sk_en('potrebné držanie (s)', 'required hold (s)'),
    'history.export_col.context': _sk_en('kontext', 'context'),
    'history.export_done': _sk_en('Uložených {n} relácií do {path}.',
                                  'Saved {n} sessions to {path}.'),
    'history.export_failed': _sk_en('Export sa nepodaril: {err}', 'Export failed: {err}'),
    'log.sessions_exported': _sk_en('Export: {n} relácií do tabuľky',
                                    'Export: {n} sessions to a spreadsheet'),
    # nazvy stlpcov v tabulke
    'history.export_col.date': _sk_en('Dátum', 'Date'),
    'history.export_col.start': _sk_en('Začiatok', 'Start'),
    'history.export_col.duration_min': _sk_en('Dĺžka (min)', 'Length (min)'),
    'history.export_col.avg_bpm': _sk_en('Priemerný tep', 'Average BPM'),
    'history.export_col.min_bpm': _sk_en('Najnižší tep', 'Lowest BPM'),
    'history.export_col.max_bpm': _sk_en('Najvyšší tep', 'Highest BPM'),
    'history.export_col.baseline_bpm': _sk_en('Pokojová základňa', 'Resting baseline'),
    'history.export_col.over_min': _sk_en('Nad hranicou (min)', 'Over limit (min)'),
    # Kluc stlpca 'breathing' (hr_stats.CSV_COLUMNS) ostava kvoli datam;
    # obsah je auto_triggers = vsetky automaticke hlasky, nie len dych.
    'history.export_col.breathing': _sk_en('Hlášky od appky', 'Cues from the app'),
    'history.export_col.peak_stress': _sk_en('Špička záťaže', 'Peak load'),
    'history.export_col.hrr_bpm': _sk_en('Zotavenie (HRR)', 'Recovery (HRR)'),
    'history.export_col.hrpi': _sk_en('HRPI', 'HRPI'),
    'history.export_col.calm_min': _sk_en('Pokoj (min)', 'Calm (min)'),
    'history.export_col.raised_min': _sk_en('Zvýšená (min)', 'Raised (min)'),
    'history.export_col.high_min': _sk_en('Vysoká (min)', 'High (min)'),
    'history.export_col.critical_min': _sk_en('Špička (min)', 'Peak (min)'),
    # 0.2: pokrytie signalu (hr_stats.pokrytie_signalu)
    'history.export_col.signal': _sk_en('signál %', 'signal %'),
    # 0.2: svet relacie, vypadky tepu, slepy cas a pauzy vo vstupe - na konci
    'history.export_col.world': _sk_en('svet', 'world'),
    'history.export_col.dropouts': _sk_en('výpadky tepu', 'heart-rate dropouts'),
    'history.export_col.blind_s': _sk_en('bez signálu (s)', 'without signal (s)'),
    'history.export_col.pause_episodes': _sk_en('pauzy vo vstupe', 'input pauses'),

    # uistenie o lokalnych datach - aj v onboardingu, hned pri anti-cheate
    'ob.step2.tag_local': _sk_en(
        'Tep aj relácie zostávajú v tvojom počítači — a kedykoľvek si ich '
        'vyexportuješ do tabuľky',
        'Heart rate and sessions stay on your computer — and you can export '
        'them to a spreadsheet any time'),

    # --- prehliadka: tepova polovica appky + pokracovanie -----------------
    'tour.sensor.title': _sk_en('Hodinky a tep', 'Watch and heart rate'),
    'tour.sensor.body': _sk_en(
        'Tu appke povieš, kde ťa má počúvať. Keď jej dáš svoj tep, ozve sa '
        'hláškou sama, keď ti záťaž chvíľu drží hore — nemusíš si na to v '
        'zápale hry spomenúť ty. Bez hodiniek sa sama neozve.',
        'This is where you tell the app where to listen. Give it your heart '
        'rate and it gives you a cue on its own when your load holds up for a '
        'while — you do not have to think of it yourself mid-game. Without a '
        'watch it will not speak up on its own.'),
    'tour.today.title': _sk_en('Čo z tepu uvidíš', 'What you see from your pulse'),
    'tour.today.body': _sk_en(
        'Stopa relácie ukazuje celý večer naraz — kde tep vyskočil a ako dlho '
        'tam ostal. Vedľa nej vidíš, koľko času si strávil v ktorom pásme. '
        'Karty hore si vieš vymeniť za tie, ktoré ťa zaujímajú.',
        'The session trace shows the whole evening at once — where your pulse '
        'spiked and how long it stayed. Next to it you see how much time you '
        'spent in each zone. The cards above can be swapped for the ones you care about.'),
    'tour.history.title': _sk_en('História relácií', 'Session history'),
    'tour.history.body': _sk_en(
        'Po pár reláciách tu uvidíš vývoj — pokojovú základňu, zotavenie tepu '
        'aj mriežku dní, v ktoré si hral. Kliknutím na riadok si ktorúkoľvek '
        'reláciu pozrieš zblízka.',
        'After a few sessions you will see the trend here — resting baseline, '
        'heart rate recovery and a grid of the days you played. Click a row to '
        'look at any session up close.'),
    'settings.tour_row_at': _sk_en('Prehliadka appky — krok {n} z {total}',
                                   'App tour — step {n} of {total}'),
    'settings.tour_resume': _sk_en('Pokračovať', 'Continue'),

    # --- QR na appku do telefonu ------------------------------------------
    # Kod je navonok skryty za znackou (biely stvorec v tmavom paneli kricí
    # a kto appku uz ma, ten ho nechce vidiet) - popisky su preto pre
    # prepinac, nie pre obrazok.
    'hr.qr_show': _sk_en('Naskenovať telefónom', 'Scan with your phone'),
    'hr.qr_hide': _sk_en('Skryť kódy', 'Hide the codes'),
    'hr.qr_android': _sk_en(
        'Android / Wear OS\n„HeartRateOnStream for OBS“ (zdarma).\n'
        'V nej nastav IP a port tohto PC.',
        'Android / Wear OS\n"HeartRateOnStream for OBS" (free).\n'
        'Set this PC\'s IP and port inside it.'),
    # iPhone (0.2): cesta je v kode, ale nevyskusana - autor nema zariadenie
    # od Apple a PulseOSC je platena. Hrac si ju nesmie kupit na zaklade
    # vety, ktoru nikto neoveril.
    'hr.qr_ios': _sk_en(
        'iPhone / Apple Watch\n„PulseOSC“ (platená).\nZatiaľ nevyskúšané.\n'
        'V nej nastav IP a port tohto PC.',
        'iPhone / Apple Watch\n"PulseOSC" (paid).\nNot tested yet.\n'
        'Set this PC\'s IP and port inside it.'),
    'hr.qr_note': _sk_en(
        'Obe appky sú cudzie, nie naše — my ich len vieme počúvať.',
        'Both apps belong to someone else, not us — we just listen to them.'),
    # Povodny text sluboval "HeartRateOnStream (Google Play / App Store)" -
    # lenze tá appka na App Store nie je a na iPhone ziadna appka
    # protokolom obs-websocket nehovori. Na iOS treba OSC (PulseOSC).
    'hr.step2_body': _sk_en(
        'Android / Wear OS: „HeartRateOnStream for OBS“ z Google Play (zdarma). '
        'iPhone / Apple Watch: „PulseOSC“ z App Store (platená) — posiela OSC '
        'a kód appky ho vie prijať, ale cesta cez iPhone je zatiaľ '
        'nevyskúšaná: autor nemá zariadenie od Apple. Ak ju skúsiš, daj vedieť, '
        'či ti ide. Heslo, scéna a zdroj v ďalších krokoch sa týkajú len appky '
        'pre Android; v PulseOSC zadáš len IP a port. Naskenuj kód nižšie a '
        'prepoj appku s hodinkami.',
        'Android / Wear OS: "HeartRateOnStream for OBS" from Google Play (free). '
        'iPhone / Apple Watch: "PulseOSC" from the App Store (paid) — it sends '
        'OSC, which the app\'s code can receive, but the iPhone route is untested '
        'so far: the author has no Apple device. If you try it, let me know '
        'whether it works for you. The password, scene and source in the next '
        'steps apply to the Android app only; in PulseOSC you only enter the IP '
        'and port. Scan a code below and connect the app to your watch.'),

    # --- onboarding: opravy prvych styroch krokov -------------------------
    # Stvrty piktogram (appka instaluje STYRI spustace, krok ukazoval tri),
    # veta o mechanizme (nikde v uvode nebolo, ze to visi na klavesoch, ktore
    # hrac aj tak tlaci) a CTA, ktore nesluboval vstup do hry.
    'ob.step1.cap_release': _sk_en('Uvoľni ruku', 'Loosen grip'),
    # 0.2 (stress-gate): „v najbližšej prestávke" už neplatí - preklady,
    # ktoré to sľubovali, sú preč (dopĺňajú sa v jazykovej fáze).
    'ob.step1.how': _sk_en(
        'Nemusíš nič stláčať ani si nič pamätať — appka sleduje tvoje zaťaženie a ozve sa sama v prestávke, keď už zaťaženie nestúpa. Kým je tvoj tep v pásme Špička, radšej mlčí.',
        'You do not have to press or remember anything — the app watches your load and speaks up by itself in a break, once the load has stopped climbing. While your pulse is in the peak zone, it stays quiet.'),
    'onboarding.confirm': _sk_en('Hotovo — spustiť', 'Done — start'),
    'ob.step3.later_note': _sk_en(
        'Nechceš teraz? Pokračuj tlačidlom Ďalej — spárovať sa dá kedykoľvek '
        'vo „V hre → Ako spárovať hodinky“.',
        'Not now? Just hit Next — you can pair any time under "In game → How to '
        'pair a watch".'),

    'log.audio_reset': _sk_en('Zvuk vrátený na odporúčané hodnoty',
                              'Sound restored to recommended values'),

    'history.pick_metric': _sk_en('Metrika', 'Metric'),
    'history.pick_period': _sk_en('Obdobie', 'Period'),
    'history.band_label': _sk_en('tvoje bežné rozpätie', 'your usual range'),
    'history.unit.baseline': _sk_en('BPM', 'BPM'),
    'history.unit.hrr': _sk_en('BPM za minútu', 'BPM per minute'),
    'history.unit.over': _sk_en('minúty', 'minutes'),
    'history.unit.peak': _sk_en('z 0–100', 'of 0-100'),
    # 0.2: bod grafu je priemer NA RELACIU v danom dni / mesiaci
    'history.unit.session_len': _sk_en('minúty na reláciu', 'minutes per session'),
    'history.unit.calm_time': _sk_en('minúty na reláciu', 'minutes per session'),
    'history.unit.signal': _sk_en('% času s tepom', '% of the time with a pulse'),
    'history.unit.breath': _sk_en('priemer na reláciu', 'average per session'),

    # 0.2: nadpis netvrdi, ze hlaska "zabera" - graf je len posun tepu po
    # hlaske a hint pod nim hovori, ze to nie je dokaz.
    'history.effect_title': _sk_en('Ako sa hýbal tep po hláške',
                                   'How your pulse moved after a cue'),
    # 0.2 (rebrik + brana): hlaska chodi az ked zataz nestupa, takze pokles
    # po nej je ciastocne vstavany - veta to musi povedat. Stary _tr7
    # preklad zmazany, aby stare znenie neprezilo v ziadnom jazyku.
    'history.effect_hint': _sk_en(
        'Posun tepu po hláške, ktorá zaznela (len hra). Vľavo od stredu znamená, že tep klesol — ale tep klesá aj sám a hláška teraz chodí, až keď záťaž už nestúpa, takže pokles po nej nie je dôkaz, že zabrala. Tenká čiarka je rozsah, v ktorom sa skutočná hodnota pravdepodobne nachádza — kým presahuje stred, rozdiel môže byť aj opačný.',
        'How your pulse moved after a cue that made a sound (play only). Left of centre means it dropped — but your pulse also drops on its own, and cues now come only once your load has stopped climbing, so a drop after a cue is no proof it worked. The thin line is the range the true value likely sits in — while it crosses the centre, the difference could go either way.'),
    'history.effect_few': _sk_en('zatiaľ {n} — málo na tvrdenie',
                                 'only {n} so far — too few to say'),
    'history.effect_empty': _sk_en(
        'Zatiaľ nezaznela ani jedna hláška, z ktorej by sa dalo merať.',
        'No cue has been delivered yet that could be measured.'),
    'cue.category.grounding': _sk_en('ťažisko', 'grounding'),
    'cue.category.jaw': _sk_en('čeľusť', 'jaw'),
    'cue.category.release': _sk_en('uvoľnenie', 'release'),
    'cue.category.breath': _sk_en('dych', 'breath'),
    'history.rhythm_title': _sk_en('Pravidelnosť', 'Consistency'),
    # Pocet dni, NIE neprerusena seria. Seria z appky vypadla zamerne:
    # je to jediny prvok, ktory sa da pretrhnut, a appka ma upokojovat.
    # Toto cislo hovori to iste ("chodis na to"), ale nic sa v nom neda
    # stratit jednym vynechanym vecerom.
    'history.days_played': _sk_en('Dní s reláciou · rok', 'Days with a session · year'),
    'history.grid_less': _sk_en('menej', 'less'),
    'history.grid_more': _sk_en('viac', 'more'),

    'history.detail_title': _sk_en('Relácia zblízka', 'One session up close'),
    'history.detail_peak': _sk_en('Najvyšší tep', 'Highest heart rate'),
    'history.detail_hrr': _sk_en('Zotavenie', 'Recovery'),
    'history.detail_breath': _sk_en('Hlášky', 'Cues'),
    'history.detail_hrpi': _sk_en('HRPI', 'HRPI'),
    # 0.2: detail ukazuje vsetky hodnoty relacie; ostatne popisky su slova
    # z tabulky (history.col_*)
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
# DOPREKLAD do ja / zh / ru / es / de / fr / pt
# ==========================================================================
#
# Kluce definovane cez `_sk_en()` maju ostatnych sedem jazykov docasne po
# anglicky. Tu sa dopĺňajú - `_tr7` prepise len tych sedem a sk/en necha
# tak, takze sa zdrojove znenie neduplikuje a nemoze sa rozist.
#
# POZN: preklady su strojove (Claude). Pre siroke vydanie, najma obsah v
# `guide.*` (biomechanika a dychove techniky, kde presnost formulacie ma
# realny vyznam), odporucame necha' ich prejst rodenym hovoriacim.

def _tr7(key, ja, zh, ru, es, de, fr, pt):
    """Doplni sedem jazykov ku klucu, ktory uz ma sk a en."""
    entry = STRINGS.get(key)
    if entry is None:
        return
    entry.update({"ja": ja, "zh": zh, "ru": ru, "es": es, "de": de,
                  "fr": fr, "pt": pt})

# --- davka 1: navigacia, dok, onboarding, spustace ------------------------
# „alpha" sa nechava v anglickom tvare aj v ostatnych jazykoch - je to
# zauzivane oznacenie stadia, nie slovo na prekladanie.
_tr7('app.version_short', 'alpha 0.2.1', 'alpha 0.2.1', 'alpha 0.2.1', 'alpha 0.2.1', 'Alpha 0.2.1', 'alpha 0.2.1', 'alpha 0.2.1')
_tr7('common.open', '開く', '打开', 'Открыть', 'Abrir', 'Öffnen', 'Ouvrir', 'Abrir')
_tr7('dialog.timing_title', 'タイミング', '时机', 'Тайминг', 'Tiempos', 'Timing', 'Rythme', 'Tempo')
_tr7('dock.pulse_live_tip', '心拍を受信中', '正在接收心率', 'Пульс поступает', 'Pulso en directo', 'Puls kommt an', 'Le pouls arrive', 'Pulso ao vivo')
_tr7('dock.start', '▶  開始', '▶  开始', '▶  Запустить', '▶  Iniciar', '▶  Starten', '▶  Démarrer', '▶  Iniciar')
_tr7('dock.stop', '■  停止', '■  停止', '■  Остановить', '■  Detener', '■  Stoppen', '■  Arrêter', '■  Parar')
_tr7('dock.stop_tip', '監視を停止 — 再開するまで何も鳴らない', '停止监听 — 重新开始前不会触发任何内容', 'Перестать слушать — пока не запустишь снова, ничего не сработает', 'Deja de escuchar: no se dispara nada hasta que vuelvas a empezar', 'Nicht mehr zuhören — bis zum Neustart passiert nichts', "Arrêter d'écouter — plus rien ne se déclenche jusqu'au redémarrage", 'Para de ouvir — nada dispara até você recomeçar')
_tr7('engine.edge', '自然な音声（Edge、準備にネット接続が必要）', '自然语音（Edge，准备时需要联网）', 'Естественный голос (Edge, для подготовки нужен интернет)', 'Voz natural (Edge, necesita internet para prepararse)', 'Natürliche Stimme (Edge, braucht Internet zur Vorbereitung)', 'Voix naturelle (Edge, nécessite internet pour la préparation)', 'Voz natural (Edge, precisa de internet para preparar)')
_tr7('engine.sapi', 'Windows の音声（オフラインでも動く）', 'Windows 语音（离线也能用）', 'Голос Windows (работает без интернета)', 'Voz de Windows (funciona sin conexión)', 'Windows-Stimme (funktioniert offline)', 'Voix Windows (fonctionne hors ligne)', 'Voz do Windows (funciona offline)')
_tr7('kamae.running','監視中', '监听中', 'Слушаю', 'Escuchando', 'Hört zu', 'À l’écoute', 'Ouvindo')
_tr7('kamae.running_sub', '心拍を見ながら、いい頃合いを待っています。', '正在关注心率，等待合适的时机。', 'Слежу за пульсом и жду подходящий момент.', 'Vigilo tu pulso y espero el momento adecuado.', 'Ich beobachte deinen Puls und warte auf den richtigen Moment.', 'Je surveille ton pouls et j’attends le bon moment.', 'Acompanho o seu pulso e espero o momento certo.')
_tr7('sidebar.state_tip', '緑 — 監視中。赤 — 停止中。「今日」ページのバーで開始できます。', '绿色 — 正在监听。红色 — 未监听。可在「今天」页面的横条开始。', 'Зелёный — приложение слушает. Красный — нет. Запуск в полосе на странице «Сегодня».', 'Verde: la app escucha. Rojo: no. Se inicia en la barra de la página Hoy.', 'Grün — die App hört zu. Rot — nicht. Starten kannst du sie in der Leiste auf der Seite Heute.', 'Vert — l’app écoute. Rouge — non. Tu la démarres dans la barre de la page Aujourd’hui.', 'Verde — o app está ouvindo. Vermelho — não está. Você o inicia na barra da página Hoje.')
_tr7('kamae.armed', '構えました', '已蓄势', 'Наготове', 'Preparada', 'Bereit', 'Prête', 'Pronta')
_tr7('kamae.armed_sub', '体がしばらく上がっています。いい頃合いを待ちます。', '你的身体已经紧绷了一阵子。我会等一个合适的时机。', 'Тело уже какое-то время на взводе. Подожду подходящий момент.', 'Llevas un rato con el cuerpo tenso. Esperaré un buen momento.', 'Dein Körper ist schon eine Weile oben. Ich warte auf einen guten Moment.', 'Ton corps est tendu depuis un moment. J’attendrai le bon moment.', 'O seu corpo está em tensão há algum tempo. Vou esperar um bom momento.')
_tr7('dnes.lastcue', '最後に話したのは {min} 分前 · {label}', '上次开口是 {min} 分钟前 · {label}', 'В последний раз — {min} мин назад · {label}', 'Habló por última vez hace {min} min · {label}', 'Zuletzt vor {min} Min · {label}', 'Dernière fois il y a {min} min · {label}', 'Falou pela última vez há {min} min · {label}')
_tr7('dnes.lastcue_now', 'たった今話しました · {label}', '刚刚开口 · {label}', 'Только что · {label}', 'Acaba de hablar · {label}', 'Gerade eben · {label}', 'À l’instant · {label}', 'Acabou de falar · {label}')
_tr7('kamae.stopped', '停止中', '已停止', 'Остановлено', 'Detenido', 'Gestoppt', 'Arrêté', 'Parado')
_tr7('kamae.stopped_sub', '何も見ていません。左のボタンで開始できます。', '什么都没在看。用左边的按钮开始。', 'Ничего не отслеживаю. Запусти кнопкой слева.', 'No vigilo nada. Iníciame con el botón de la izquierda.', 'Ich beobachte nichts. Starte mich mit dem Knopf links.', 'Je ne surveille rien. Démarre-moi avec le bouton à gauche.', 'Não estou acompanhando nada. Você me inicia com o botão à esquerda.')
_tr7('mode.combo', '音声＋効果音', '语音 + 音效', 'Голос + звук', 'Voz + sonido', 'Stimme + Ton', 'Voix + son', 'Voz + som')
_tr7('mode.sfx', '効果音', '音效', 'Звук', 'Sonido', 'Ton', 'Son', 'Som')
_tr7('mode.tts', '音声', '语音', 'Голос', 'Voz', 'Stimme', 'Voix', 'Voz')
_tr7('nav.dnes', '今日', '今天', 'Сегодня', 'Hoy', 'Heute', "Aujourd'hui", 'Hoje')
_tr7('nav.guide', 'ガイド', '指南', 'Справочник', 'Guía', 'Leitfaden', 'Guide', 'Guia')
_tr7('nav.historia', '履歴', '历史', 'История', 'Historial', 'Verlauf', 'Historique', 'Histórico')
_tr7('nav.nastavenia_tabs.guide', 'ガイド', '指南', 'Справочник', 'Guía', 'Leitfaden', 'Guide', 'Guia')
_tr7('nav.nastavenia_tabs.spustace', 'トリガー', '触发器', 'Триггеры', 'Disparadores', 'Trigger', 'Déclencheurs', 'Gatilhos')
_tr7('nav.nastavenia_tabs.vhre', 'ゲーム中', '游戏中', 'В игре', 'En el juego', 'Im Spiel', 'En jeu', 'No jogo')
_tr7('nav.nastavenia_tabs.vseobecne', '全般', '通用', 'Общие', 'General', 'Allgemein', 'Général', 'Geral')
_tr7('nav.nastavenia_tabs.zvuk', 'サウンド', '声音', 'Звук', 'Sonido', 'Ton', 'Son', 'Som')
_tr7('nav.spustace', 'トリガー', '触发器', 'Триггеры', 'Disparadores', 'Trigger', 'Déclencheurs', 'Gatilhos')
_tr7('nav.vhre', '時計とゲーム中', '手表与游戏中', 'Часы и в игре', 'Reloj y en el juego', 'Uhr und im Spiel', 'Montre et en jeu', 'Relógio e no jogo')
_tr7('nav.zvuk', 'サウンド / オーディオ', '声音 / 音频', 'Звук / Аудио', 'Sonido / Audio', 'Ton / Audio', 'Son / Audio', 'Som / Áudio')
_tr7('ob.back', '戻る', '返回', 'Назад', 'Atrás', 'Zurück', 'Retour', 'Voltar')
_tr7('ob.next', '次へ', '下一步', 'Далее', 'Siguiente', 'Weiter', 'Suivant', 'Próximo')
_tr7('ob.skip', 'イントロをスキップ', '跳过介绍', 'Пропустить вступление', 'Saltar la introducción', 'Intro überspringen', "Passer l'intro", 'Pular a introdução')
_tr7('ob.step1.title', 'ゲーム中にアプリが思い出させてくれること', '游戏中，应用会提醒你这些', 'Вот о чём приложение напомнит тебе в игре', 'Esto es lo que la app te recuerda en plena partida', 'Daran erinnert dich die App mitten im Spiel', 'Voici ce que l’app te rappelle en pleine partie', 'É disso que o app te lembra no meio do jogo')
_tr7('ob.step1.cap_grounding', '重心', '重心', 'Центр тяжести', 'Centro', 'Schwerpunkt', 'Ancrage', 'Centro')
_tr7('ob.step1.cap_jaw', '顎をゆるめる', '松开下巴', 'Расслабь челюсть', 'Afloja la mandíbula', 'Kiefer lockern', 'Relâche la mâchoire', 'Solta o maxilar')
_tr7('ob.step1.cap_release', '手をゆるめる', '松开握力', 'Расслабь руку', 'Afloja la mano', 'Griff lockern', 'Relâche la main', 'Solta a mão')
_tr7('ob.step1.cap_breath', '呼吸', '呼吸', 'Дыхание', 'Respiración', 'Atem', 'Souffle', 'Respiração')
_tr7('ob.step2.title', '控えめに。邪魔にならない隅に。', '低调。在角落，不挡路。', 'Незаметно. В углу, не мешая.', 'Discreto. En una esquina, sin estorbar.', 'Unaufdringlich. In der Ecke, nicht im Weg.', 'Discret. Dans un coin, hors du passage.', 'Discreto. Num canto, fora do caminho.')
_tr7('ob.step2.body', '合図は画面の端に出て、すぐ消える — クロスヘアやキルフィードを隠すことはない。位置は好きなところへドラッグでき、ゲーム中のクリックはそのままゲームに通る。', '提示出现在屏幕边缘随后淡出 — 绝不遮挡准星或击杀信息。位置可以随意拖动，游戏中的点击会直接穿透到游戏里。', 'Подсказки появляются у края экрана и гаснут — они никогда не закрывают прицел или киллфид. Всё можно перетащить куда хочешь, а клики в игре проходят прямо в игру.', 'Los avisos aparecen en el borde de la pantalla y se desvanecen: nunca tapan la mira ni el killfeed. Todo se puede arrastrar donde quieras y, en el juego, tus clics pasan directos al juego.', 'Die Hinweise erscheinen am Bildschirmrand und verschwinden wieder — sie verdecken nie Fadenkreuz oder Killfeed. Alles lässt sich hinziehen, wohin du willst, und im Spiel gehen deine Klicks direkt durch.', 'Les repères apparaissent au bord de l’écran puis s’effacent — ils ne couvrent jamais le viseur ni le killfeed. Tout se déplace où tu veux, et en jeu tes clics passent directement au jeu.', 'Os avisos aparecem na borda da tela e somem — nunca cobrem a mira nem o killfeed. Você pode arrastar tudo para onde quiser e, no jogo, os cliques passam direto para o jogo.')
_tr7('ob.step2.tag_local', '心拍もセッションもこのPCに残る — いつでも表に書き出せる', '心率和记录都留在你的电脑里 — 随时可以导出成表格', 'Пульс и сессии остаются на твоём компьютере — и в любой момент их можно выгрузить в таблицу', 'El pulso y las sesiones se quedan en tu ordenador, y puedes exportarlos a una hoja de cálculo cuando quieras', 'Puls und Sitzungen bleiben auf deinem Rechner — und du kannst sie jederzeit als Tabelle exportieren', 'Le pouls et les séances restent sur ton ordinateur — et tu peux les exporter en tableur quand tu veux', 'O pulso e as sessões ficam no seu computador — e você pode exportá-los para uma planilha quando quiser')
_tr7('ob.step3.pair_now', '今すぐ時計をつなぐ', '现在连接手表', 'Подключить часы сейчас', 'Vincular un reloj ahora', 'Jetzt eine Uhr verbinden', 'Connecter une montre maintenant', 'Parear um relógio agora')
_tr7('ob.step3.later', 'スキップ — あとでつなぐ', '跳过 — 稍后再连', 'Пропустить — подключу позже', 'Saltar: lo vinculo después', 'Überspringen — ich verbinde später', 'Passer — je connecterai plus tard', 'Pular — pareio depois')
_tr7('ob.step3.later_note', '今はいい？「次へ」を押すだけ — 時計は「ゲーム中 → 時計のつなぎ方」からいつでもつなげる。', '现在不想连？直接点“下一步”— 随时可以在“游戏中 → 如何连接手表”里配对。', 'Не сейчас? Просто нажми «Далее» — подключить часы можно когда угодно в «В игре → Как подключить часы».', '¿Ahora no? Pulsa Siguiente: puedes vincularlo cuando quieras en «En el juego → Cómo vincular un reloj».', 'Jetzt nicht? Klick einfach auf Weiter — verbinden kannst du jederzeit unter „Im Spiel → Uhr verbinden“.', 'Pas maintenant ? Clique sur Suivant — tu peux connecter à tout moment dans « En jeu → Connecter une montre ».', 'Agora não? Clique em Próximo — você pode parear quando quiser em “No jogo → Como parear o seu relógio”.')
_tr7('onboarding.confirm', '完了 — 開始', '完成 — 开始', 'Готово — запустить', 'Listo: empezar', 'Fertig — starten', 'Terminé — démarrer', 'Pronto — iniciar')
_tr7('slot.file_short', 'ファイル', '文件', 'Файл', 'Archivo', 'Datei', 'Fichier', 'Arquivo')
_tr7('slot.record_short', '録音', '录音', 'Запись', 'Grabar', 'Aufnehmen', 'Enregistrer', 'Gravar')
_tr7('slots.title', 'アプリが言うこと', '应用会说什么', 'Что говорит приложение', 'Lo que dice la app', 'Was die App sagt', 'Ce que dit l’app', 'O que o app diz')
_tr7('slots.clear_selection', '選択を解除', '取消选择', 'Снять выделение', 'Quitar selección', 'Auswahl aufheben', 'Annuler la sélection', 'Limpar seleção')
_tr7('slots.remove_selected', '選択したものを削除', '删除所选', 'Удалить выбранные', 'Eliminar seleccionados', 'Ausgewählte entfernen', 'Supprimer la sélection', 'Remover selecionados')
_tr7('slots.selected_count', '選択中: {n}', '已选：{n}', 'Выбрано: {n}', 'Seleccionados: {n}', 'Ausgewählt: {n}', 'Sélectionnés : {n}', 'Selecionados: {n}')
_tr7('slots.remove_confirm', '選択した {n} 個のトリガーを削除する？\n\n{list}', '删除所选的 {n} 个触发器？\n\n{list}', 'Удалить {n} выбранных триггеров?\n\n{list}', '¿Eliminar los {n} disparadores seleccionados?\n\n{list}', '{n} ausgewählte Trigger entfernen?\n\n{list}', 'Supprimer les {n} déclencheurs sélectionnés ?\n\n{list}', 'Remover os {n} gatilhos selecionados?\n\n{list}')
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
_tr7('dnes.hr_connected', '時計に接続済み', '手表已连接', 'часы подключены', 'reloj conectado', 'Uhr verbunden', 'montre connectée', 'relógio conectado')
_tr7('dnes.hr_waiting', '時計を待っています', '等待手表', 'жду часы', 'esperando al reloj', 'warte auf die Uhr', 'en attente de la montre', 'aguardando o relógio')
_tr7('dnes.empty_title', 'ここに心拍が出ます', '你的心率会显示在这里', 'Здесь появится твой пульс', 'Aquí aparecerá tu pulso', 'Hier erscheint dein Puls', 'Ton pouls apparaîtra ici', 'O seu pulso aparece aqui')
_tr7('dnes.empty_btn', '時計をつなぐ', '连接手表', 'Подключить часы', 'Vincular el reloj', 'Uhr verbinden', 'Connecter la montre', 'Parear o relógio')
_tr7('dnes.trace_title', 'セッションの軌跡', '本次轨迹', 'След сессии', 'Rastro de la sesión', 'Spur der Sitzung', 'Trace de la séance', 'Rastro da sessão')
_tr7('dnes.zones_title', 'セッションの内訳', '这次都在哪个区间', 'Где прошла сессия', 'Dónde fue la sesión', 'Wo die Sitzung lag', 'Où la séance s’est passée', 'Onde a sessão passou')
_tr7('dnes.zones_hint', 'セッションのうち、どの帯にどれだけいたか。帯は自分の安静時ベースラインを基準に測る — 表の数値ではない。', '本次记录中你在各区间待了多久。区间以你自己的静息基线为准，而不是表格数值。', 'Сколько времени за сессию ты провёл в каждой зоне. Зоны считаются от твоей собственной базовой линии покоя, а не от табличного значения.', 'Cuánto de la sesión pasaste en cada zona. Las zonas se miden frente a tu propia línea base en reposo, no frente a un valor de tabla.', 'Wie viel der Sitzung du in welcher Zone verbracht hast. Die Zonen messen gegen deine eigene Ruhebasislinie, nicht gegen einen Tabellenwert.', 'Combien de la séance tu as passé dans chaque zone. Les zones se mesurent par rapport à ta propre ligne de base au repos, pas à une valeur de table.', 'Quanto da sessão você passou em cada zona. As zonas são medidas em relação à sua própria linha de base em repouso, não a um valor de tabela.')
_tr7('dnes.session_title', 'このセッション', '本次记录', 'Эта сессия', 'Esta sesión', 'Diese Sitzung', 'Cette séance', 'Esta sessão')
_tr7('dnes.stat_min', '最低', '最低', 'Минимум', 'Mínimo', 'Tiefstwert', 'Minimum', 'Mínimo')
_tr7('dnes.stat_avg', '平均', '平均', 'Среднее', 'Media', 'Durchschnitt', 'Moyenne', 'Média')
_tr7('dnes.stat_max', '最高', '最高', 'Максимум', 'Máximo', 'Höchstwert', 'Maximum', 'Máximo')
_tr7('dnes.stat_over', 'しきい値超え', '超过阈值', 'Выше порога', 'Por encima del límite', 'Über der Grenze', 'Au-dessus du seuil', 'Acima do limite')
_tr7('dnes.stat_hrr', '心拍回復（HRR）', '心率恢复（HRR）', 'Восстановление пульса (HRR)', 'Recuperación del pulso (HRR)', 'Herzfrequenz-Erholung (HRR)', 'Récupération cardiaque (HRR)', 'Recuperação do pulso (HRR)')
_tr7('dnes.load_note', '心拍から、自分の安静時ベースラインを基準に算出。これは HRV ではない — 時計が送るのは1分あたりの拍数であって、拍と拍の間隔ではない。', '由心率相对你自己的静息基线推算而来。这不是 HRV — 手表发送的是每分钟心跳数，而不是心跳间隔。', 'Выводится из пульса относительно твоей собственной базовой линии покоя. Это не HRV — часы присылают удары в минуту, а не промежутки между ударами.', 'Se deriva del pulso frente a tu propia línea base en reposo. Esto no es HRV: el reloj envía latidos por minuto, no los intervalos entre latidos.', 'Abgeleitet aus dem Puls gegenüber deiner eigenen Ruhebasislinie. Das ist kein HRV — die Uhr sendet Schläge pro Minute, nicht die Abstände dazwischen.', 'Dérivé du pouls par rapport à ta propre ligne de base au repos. Ce n’est pas la VFC — la montre envoie des battements par minute, pas les intervalles entre eux.', 'Derivado do pulso em relação à sua própria linha de base em repouso. Isto não é HRV — o relógio envia batimentos por minuto, não os intervalos entre eles.')
_tr7('dnes.why_line', 'ゲーム中、気づく前に体はこわばる — Zanshin はそこに短いリセットを結びつける。', '游戏中身体在你察觉前就绷紧了 — Zanshin 把一次短暂的重置绑在那一刻。', 'В игре тело напрягается раньше, чем ты заметишь, — Zanshin привязывает к этому короткий сброс.', 'En plena partida el cuerpo se tensa antes de que lo notes: Zanshin ata un reinicio corto a ese momento.', 'Mitten im Spiel verspannt sich der Körper, bevor du es merkst — Zanshin knüpft daran einen kurzen Reset.', 'En pleine partie, le corps se crispe avant que tu le remarques — Zanshin y attache une remise à zéro courte.', 'No meio do jogo, o corpo trava antes de você perceber — o Zanshin associa a isso um reset curto.')
_tr7('tour.next', '次へ', '下一步', 'Далее', 'Siguiente', 'Weiter', 'Suivant', 'Próximo')
_tr7('tour.skip', 'スキップ', '跳过', 'Пропустить', 'Saltar', 'Überspringen', 'Passer', 'Pular')
_tr7('tour.done_btn', 'わかった', '知道了', 'Понятно', 'Entendido', 'Alles klar', 'Compris', 'Entendido')
_tr7('tour.step_of', 'ステップ {n} / {total}', '第 {n} 步，共 {total} 步', 'ШАГ {n} из {total}', 'PASO {n} de {total}', 'SCHRITT {n} von {total}', 'ÉTAPE {n} sur {total}', 'PASSO {n} de {total}')
_tr7('tour.welcome.title', 'かんたんツアー', '快速导览', 'Быстрая экскурсия', 'Recorrido rápido', 'Kurze Tour', 'Visite rapide', 'Visita rápida')
_tr7('tour.welcome.body', 'どこに何があるか案内する — 数秒で終わる。いつでもスキップできる。', '带你看看东西都在哪儿 — 只要几秒。随时可以跳过。', 'Покажу, где что находится — это пара секунд. Пропустить можно в любой момент.', 'Te enseño dónde está cada cosa: son unos segundos. Puedes saltarlo cuando quieras.', 'Ich zeige dir, wo was ist — dauert ein paar Sekunden. Du kannst jederzeit überspringen.', 'Je te montre où se trouve quoi — quelques secondes. Tu peux passer à tout moment.', 'Vou te mostrar onde fica cada coisa — leva uns segundos. Você pode pular quando quiser.')
_tr7('tour.kamae.title', '開始と停止', '开始与停止', 'Запуск и остановка', 'Iniciar y detener', 'Starten und stoppen', 'Démarrer et arrêter', 'Iniciar e parar')
_tr7('tour.triggers.title', 'トリガー', '触发器', 'Триггеры', 'Disparadores', 'Trigger', 'Déclencheurs', 'Gatilhos')
_tr7('tour.sound.title', 'サウンド', '声音', 'Звук', 'Sonido', 'Ton', 'Son', 'Som')
_tr7('tour.ingame.title', 'ゲーム中', '游戏中', 'В игре', 'En el juego', 'Im Spiel', 'En jeu', 'No jogo')
_tr7('tour.sensor.title', '時計と心拍', '手表与心率', 'Часы и пульс', 'Reloj y pulso', 'Uhr und Puls', 'Montre et pouls', 'Relógio e pulso')
_tr7('tour.today.title', '心拍から見えるもの', '从心率里能看到什么', 'Что видно по пульсу', 'Qué ves desde tu pulso', 'Was du vom Puls siehst', 'Ce que tu vois de ton pouls', 'O que você vê do seu pulso')
_tr7('tour.today.body', 'セッションの軌跡は一晩まるごとを一度に見せる — どこで心拍が跳ね、どれだけ続いたか。隣にはどの帯にどれだけいたかが出る。上のカードは自分の見たいものに入れ替えられる。', '轨迹把整晚一次看完 — 心率在哪里飙升、又持续了多久。旁边显示你在各区间待了多久。上面的卡片可以换成你关心的指标。', 'След сессии показывает весь вечер сразу — где пульс подскочил и как долго держался. Рядом видно, сколько времени ты провёл в каждой зоне. Карточки сверху можно заменить на те, что тебя интересуют.', 'El rastro muestra la velada entera de una vez: dónde se disparó el pulso y cuánto se mantuvo. Al lado ves cuánto tiempo pasaste en cada zona. Las tarjetas de arriba se pueden cambiar por las que te interesen.', 'Die Spur zeigt den ganzen Abend auf einmal — wo der Puls hochging und wie lange er blieb. Daneben siehst du, wie viel Zeit du in welcher Zone verbracht hast. Die Karten oben lassen sich gegen die tauschen, die dich interessieren.', 'La trace montre toute la soirée d’un coup — où le pouls a bondi et combien de temps il est resté. À côté, tu vois le temps passé dans chaque zone. Les cartes du haut se remplacent par celles qui t’intéressent.', 'O rastro mostra a noite inteira de uma vez — onde o pulso disparou e quanto tempo ficou. Ao lado, você vê quanto tempo passou em cada zona. Os cartões de cima podem ser trocados pelos que te interessam.')
_tr7('tour.history.title', 'セッション履歴', '记录历史', 'История сессий', 'Historial de sesiones', 'Sitzungsverlauf', 'Historique des séances', 'Histórico de sessões')
_tr7('tour.history.body', '何回かセッションを重ねると、ここに推移が出る — 安静時ベースライン、心拍回復、そして遊んだ日のグリッド。行をクリックすれば、どのセッションもじっくり見られる。', '几次记录之后，这里会显示趋势 — 静息基线、心率恢复，以及你游玩日期的格子图。点击某一行就能细看那一次。', 'После нескольких сессий здесь появится динамика — базовая линия покоя, восстановление пульса и сетка дней, когда ты играл. Клик по строке открывает любую сессию вблизи.', 'Tras unas cuantas sesiones verás aquí la evolución: línea base en reposo, recuperación del pulso y una cuadrícula de los días que jugaste. Haz clic en una fila para ver cualquier sesión de cerca.', 'Nach ein paar Sitzungen siehst du hier den Verlauf — Ruhebasislinie, Herzfrequenz-Erholung und ein Raster der Tage, an denen du gespielt hast. Ein Klick auf eine Zeile zeigt jede Sitzung aus der Nähe.', 'Après quelques séances, tu verras ici l’évolution — ligne de base au repos, récupération cardiaque et une grille des jours joués. Clique sur une ligne pour voir une séance de près.', 'Depois de algumas sessões, você vê aqui a evolução — linha de base em repouso, recuperação do pulso e uma grade dos dias em que jogou. Clique numa linha para ver qualquer sessão de perto.')
_tr7('tour.dock.title', '開始と停止', '开始与停止', 'Запуск и остановка', 'Iniciar y detener', 'Starten und stoppen', 'Démarrer et arrêter', 'Iniciar e parar')
_tr7('tour.done.title', 'これで終わり', '就这些', 'Вот и всё', 'Eso es todo', 'Das war’s', 'C’est tout', 'É tudo')
_tr7('tour.kamae.body', 'このバーが主スイッチです。左の ▶ / ▮▮ ボタンでアプリを開始・停止します。監視中はバーがゆっくり呼吸し、停止中は静かです。', '这条横条是主开关。左边的 ▶ / ▮▮ 按钮用来启动和停止应用。监听时横条会缓缓呼吸，停止时保持安静。', 'Эта полоса — главный переключатель. Кнопка ▶ / ▮▮ слева запускает и останавливает приложение. Когда оно слушает, полоса мягко дышит; когда стоит — спокойна.', 'Esta barra es el interruptor principal. El botón ▶ / ▮▮ de la izquierda inicia y detiene la app. Mientras escucha, la barra respira suavemente; parada, está quieta.', 'Diese Leiste ist der Hauptschalter. Der Knopf ▶ / ▮▮ links startet und stoppt die App. Während sie zuhört, atmet die Leiste sanft; gestoppt ist sie ruhig.', 'Cette barre est l’interrupteur principal. Le bouton ▶ / ▮▮ à gauche démarre et arrête l’app. Quand elle écoute, la barre respire doucement ; à l’arrêt, elle est immobile.', 'Esta barra é o interruptor principal. O botão ▶ / ▮▮ à esquerda inicia e para o app. Enquanto ele ouve, a barra respira devagar; parado, ela fica quieta.')
_tr7('tour.dock.body', 'これは円相（ensō）— アプリの印であり状態でもあります。緑で呼吸していれば監視中、赤で静止していれば停止中。体が高いままだと内側にゆっくりした環が現れ、いい頃合いを待っている合図です。円相はこのページにあり、他のページでは左の帯の色つきの点が状態を示します。', '这是圆相（ensō）—— 既是应用的标志，也是它的状态。绿色并在呼吸表示正在监听；红色且静止表示已停止。当身体持续紧绷时，内部会出现一个缓慢的环，表示应用正在等待合适的时机。它只在本页；在其他页面，左侧栏的彩色圆点表示状态。', 'Это энсо — знак приложения и его состояние одновременно. Зелёное и дышащее — слушает; красное и неподвижное — остановлено. Когда тело долго держится на взводе, внутри появляется медленное кольцо: приложение ждёт подходящего момента. Энсо живёт на этой странице; на остальных состояние показывает цветная точка в левой панели.', 'Esto es el ensō: la marca de la app y su estado a la vez. Verde y respirando significa que escucha; rojo e inmóvil, que está detenida. Cuando el cuerpo se mantiene tenso, aparece dentro un anillo lento: la app espera un buen momento. Vive en esta página; en las demás, el punto de color de la barra izquierda lleva el estado.', 'Das ist das Ensō — Zeichen der App und ihr Zustand zugleich. Grün und atmend heißt, sie hört zu; rot und still heißt, sie ist gestoppt. Bleibt dein Körper oben, erscheint darin ein langsamer Ring: die App wartet auf einen guten Moment. Es lebt auf dieser Seite; auf den anderen trägt der farbige Punkt in der linken Leiste den Zustand.', 'Voici l’ensō — la marque de l’app et son état à la fois. Vert et respirant : elle écoute ; rouge et immobile : elle est arrêtée. Quand ton corps reste tendu, un anneau lent apparaît à l’intérieur : l’app attend le bon moment. Il vit sur cette page ; ailleurs, le point coloré de la barre de gauche porte l’état.', 'Este é o ensō — a marca do app e o estado dele ao mesmo tempo. Verde e respirando significa que ele está ouvindo; vermelho e imóvel, que está parado. Quando o corpo se mantém em tensão, aparece lá dentro um anel lento: o app está esperando um bom momento. Ele fica nesta página; nas outras, o ponto colorido da barra à esquerda mostra o estado.')
_tr7('tour.done.body', 'このツアーは設定からいつでもやり直せる。よいゲームを。', '这个导览随时可以在设置里重看。玩得开心。', 'Эту экскурсию можно повторить в настройках когда угодно. Хорошей игры.', 'Puedes repetir este recorrido cuando quieras en Ajustes. Que disfrutes la partida.', 'Diese Tour kannst du jederzeit in den Einstellungen wiederholen. Viel Spaß beim Spielen.', 'Tu peux rejouer cette visite à tout moment dans les réglages. Bon jeu.', 'Você pode repetir esta visita quando quiser em Configurações. Bom jogo.')
_tr7('metric.bpm.title', '現在の心拍', '当前心率', 'Пульс сейчас', 'Pulso ahora', 'Puls jetzt', 'Pouls actuel', 'Pulso agora')
_tr7('metric.bpm.short', '今、心臓が1分間に何回打っているか。', '你的心脏此刻每分钟跳多少下。', 'Сколько раз в минуту сейчас бьётся твоё сердце.', 'Cuántas veces por minuto late ahora tu corazón.', 'Wie oft dein Herz gerade pro Minute schlägt.', 'Combien de fois par minute ton cœur bat en ce moment.', 'Quantas vezes por minuto o seu coração bate agora.')
_tr7('metric.bpm.more', '基本の数字。それ自体はあまり語らない — 大事なのは安静時の水準からどれだけ動くか、そして落ち着いたときにどれだけ速く下がるか。', '最基础的数字。单看它意义不大 — 重要的是它相对你的静息水平怎么动，以及你平静下来时下降得多快。', 'Базовое число. Само по себе оно мало что говорит — важно, как оно движется относительно твоего уровня покоя и как быстро падает, когда ты успокаиваешься.', 'El número base. Por sí solo dice poco: lo que importa es cómo se mueve frente a tu nivel de reposo y con qué rapidez baja cuando te calmas.', 'Die Grundzahl. Für sich allein sagt sie wenig — entscheidend ist, wie sie sich gegenüber deinem Ruheniveau bewegt und wie schnell sie fällt, wenn du runterkommst.', 'Le chiffre de base. Seul, il dit peu — ce qui compte, c’est comment il bouge par rapport à ton niveau de repos et à quelle vitesse il redescend quand tu te calmes.', 'O número básico. Sozinho diz pouco — o que importa é como ele se move em relação ao seu nível de repouso e com que rapidez desce quando você se acalma.')
_tr7('metric.baseline.tag', '安静時', '静息', 'покой', 'reposo', 'Ruhe', 'repos', 'repouso')
_tr7('metric.hrr.tag', '回復', '恢复', 'восстановление', 'recuperación', 'Erholung', 'récupération', 'recuperação')
_tr7('metric.over.tag', '超過時間', '超限', 'выше порога', 'sobre límite', 'über Grenze', 'au-dessus', 'acima')
_tr7('metric.avg.tag', '平均', '平均', 'средний', 'media', 'Schnitt', 'moyenne', 'média')
_tr7('metric.max.tag', '最高', '最高', 'максимум', 'máximo', 'Maximum', 'maximum', 'máximo')
_tr7('metric.peak.tag', '負荷ピーク', '负荷峰值', 'пик нагрузки', 'pico de carga', 'Last-Spitze', 'pic de charge', 'pico de carga')
_tr7('metric.week.tag', '今週', '本周', 'за неделю', 'esta semana', 'diese Woche', 'cette semaine', 'esta semana')
_tr7('metric.baseline.title', '安静時ベースライン', '静息基线', 'Базовая линия покоя', 'Línea base en reposo', 'Ruhebasislinie', 'Ligne de base au repos', 'Linha de base em repouso')
_tr7('metric.baseline.short', 'ゲームに押されていないときの、あなたの心拍。', '游戏没有给你压力时的心率。', 'Твой пульс, когда игра тебя никуда не гонит.', 'Tu pulso cuando el juego no te está exigiendo.', 'Dein Puls, wenn dich das Spiel nicht drängt.', 'Ton pouls quand le jeu ne te pousse pas.', 'O seu pulso quando o jogo não te pressiona.')
_tr7('metric.baseline.more', 'アプリは最も落ち着いた瞬間から算出する。日ごとに上がっていくなら、体が疲れているかストレスがあるのかもしれない — 必ずしもゲームのせいではない（睡眠、カフェイン、体調）。だから一つの数字ではなく、時間の流れで追う。', '应用从你最平静的时刻推算。如果它一天天升高，可能是身体疲惫或压力大 — 不一定是游戏造成的（睡眠、咖啡因、生病）。所以我们看的是长期走势，而不是单个数字。', 'Приложение выводит её из самых спокойных моментов. Если она растёт день за днём, тело может быть уставшим или в стрессе — не обязательно из-за игры (сон, кофеин, болезнь). Поэтому мы следим за ней во времени, а не по одному числу.', 'La app la deduce de tus momentos más tranquilos. Si sube día tras día, tu cuerpo puede estar cansado o estresado, no necesariamente por jugar (sueño, cafeína, enfermedad). Por eso la seguimos en el tiempo y no como un número suelto.', 'Die App leitet sie aus deinen ruhigsten Momenten ab. Steigt sie Tag für Tag, ist dein Körper vielleicht müde oder gestresst — nicht zwangsläufig vom Spielen (Schlaf, Koffein, Krankheit). Deshalb verfolgen wir sie über die Zeit, nicht als Einzelwert.', 'L’app la déduit de tes moments les plus calmes. Si elle monte jour après jour, ton corps est peut-être fatigué ou stressé — pas forcément à cause du jeu (sommeil, caféine, maladie). C’est pourquoi on la suit dans le temps, pas comme un chiffre isolé.', 'O app a deduz da sua fase mais calma. Se ela sobe dia após dia, o corpo pode estar cansado ou estressado — não necessariamente por causa do jogo (sono, cafeína, doença). Por isso a acompanhamos ao longo do tempo, não como um número isolado.')
_tr7('metric.load.title', '負荷', '负荷', 'Нагрузка', 'Carga', 'Last', 'Charge', 'Carga')
_tr7('metric.hrr.title', '心拍回復（HRR）', '心率恢复（HRR）', 'Восстановление пульса (HRR)', 'Recuperación del pulso (HRR)', 'Herzfrequenz-Erholung (HRR)', 'Récupération cardiaque (HRR)', 'Recuperação do pulso (HRR)')
_tr7('metric.hrr.short', '心拍が跳ね上がったあと、1分でどれだけ下がったか。', '心率飙升之后，一分钟内下降了多少。', 'На сколько упал пульс за минуту после скачка.', 'Cuánto bajó tu pulso en el minuto siguiente a un pico.', 'Um wie viel dein Puls in der Minute nach einem Ausschlag gefallen ist.', 'De combien ton pouls est redescendu dans la minute suivant un pic.', 'Quanto o seu pulso desceu no minuto seguinte a um pico.')
_tr7('metric.zones.title', 'しきい値超え / 帯ごとの時間', '超阈值时间 / 各区间时间', 'Время выше порога / по зонам', 'Tiempo sobre el límite / por zonas', 'Zeit über der Grenze / in Zonen', 'Temps au-dessus du seuil / par zones', 'Tempo acima do limite / por zonas')
_tr7('metric.zones.short', 'セッションのうち、心拍が高いまま過ごした割合。', '本次记录里你心率偏高的时间占多少。', 'Сколько времени за сессию ты провёл с высоким пульсом.', 'Cuánto de la sesión pasaste con el pulso alto.', 'Wie viel der Sitzung du mit hohem Puls verbracht hast.', 'Combien de la séance tu as passé avec un pouls élevé.', 'Quanto da sessão você passou com o pulso alto.')
_tr7('metric.zones.calm', '平静', '平静', 'покой', 'calma', 'ruhig', 'calme', 'calmo')
_tr7('metric.zones.raised', 'やや上昇', '略高', 'повышенная', 'elevada', 'erhöht', 'élevée', 'elevada')
_tr7('metric.zones.high', '高い', '偏高', 'высокая', 'alta', 'hoch', 'haute', 'alta')
_tr7('metric.zones.critical', 'ピーク', '高峰', 'пик', 'pico', 'Spitze', 'pic', 'pico')
_tr7('metric.hrpi.title', 'HRPI', 'HRPI', 'HRPI', 'HRPI', 'HRPI', 'HRPI', 'HRPI')
_tr7('metric.hrpi.short', '心拍がどれだけ高く、どれだけ長く続いたかを一つにまとめた数字。', '把心率有多高、持续多久合成一个数字。', 'Одно число, связывающее, насколько высоко и как долго шёл твой пульс.', 'Un número que une lo alto y lo largo que estuvo tu pulso.', 'Eine Zahl, die verbindet, wie hoch und wie lange dein Puls lief.', 'Un chiffre qui relie la hauteur et la durée de ton pouls.', 'Um número que junta o quão alto e por quanto tempo o seu pulso esteve.')
_tr7('metric.hrpi.more', '値 k は、心拍が少なくとも k 秒のあいだ、少なくとも毎分 k 拍あったという意味。高さと長さを一つにまとめるので、二つのセッションを一目で比べられる。', '数值 k 表示你的心率至少达到每分钟 k 次，并持续至少 k 秒。它把高度和时长合为一体，让你一眼就能比较两次记录。', 'Значение k означает, что пульс был не ниже k ударов в минуту в течение не менее k секунд. Оно соединяет высоту и длительность, так что две сессии можно сравнить одним взглядом.', 'Un valor k significa que tu pulso estuvo al menos a k latidos por minuto durante al menos k segundos. Une altura y duración, así que puedes comparar dos sesiones de un vistazo.', 'Ein Wert k heißt: Dein Puls lag mindestens k Schläge pro Minute für mindestens k Sekunden. Er verbindet Höhe und Dauer, sodass du zwei Sitzungen auf einen Blick vergleichen kannst.', 'Une valeur k signifie que ton pouls était d’au moins k battements par minute pendant au moins k secondes. Elle joint hauteur et durée, si bien que tu compares deux séances d’un coup d’œil.', 'Um valor k significa que o seu pulso ficou em pelo menos k batimentos por minuto durante pelo menos k segundos. Junta altura e duração, por isso você compara duas sessões num relance.')
_tr7('metric.over.title', 'しきい値超えの時間', '超过阈值的时间', 'Время выше порога', 'Tiempo sobre el límite', 'Zeit über der Grenze', 'Temps au-dessus du seuil', 'Tempo acima do limite')
_tr7('metric.avg.title', '今日の平均心拍', '今日平均心率', 'Средний пульс сегодня', 'Pulso medio de hoy', 'Durchschnittspuls heute', 'Pouls moyen aujourd’hui', 'Pulso médio hoje')
_tr7('metric.avg.short', '今日のセッション全体の平均心拍。', '今天整场记录的平均心率。', 'Твой средний пульс за всю сегодняшнюю сессию.', 'Tu pulso medio en toda la sesión de hoy.', 'Dein Durchschnittspuls über die gesamte heutige Sitzung.', 'Ton pouls moyen sur toute la séance du jour.', 'O seu pulso médio em toda a sessão de hoje.')
_tr7('metric.avg.more', 'セッション全体を一つの数字にしたもの — 日々の比較には安静時ベースラインのほうが役に立つ。あちらは最も落ち着いた瞬間だけを数えるから。', '把整场记录压成一个数字 — 但要做日常比较，静息基线更有用，因为它只统计你最平静的时刻。', 'Одно число на всю сессию — для сравнения день ко дню полезнее базовая линия покоя: она считает только самые спокойные моменты.', 'Un número para toda la sesión: para comparar día a día es más útil la línea base en reposo, porque solo cuenta tus momentos más tranquilos.', 'Eine Zahl für die ganze Sitzung — für den Vergleich von Tag zu Tag ist die Ruhebasislinie nützlicher, denn sie zählt nur deine ruhigsten Momente.', 'Un chiffre pour toute la séance — pour comparer d’un jour à l’autre, la ligne de base au repos est plus utile : elle ne compte que tes moments les plus calmes.', 'Um número para toda a sessão — para comparar dia a dia, a linha de base em repouso é mais útil, porque só conta os seus momentos mais calmos.')
_tr7('metric.max.title', '最高心拍', '最高心率', 'Самый высокий пульс', 'Pulso más alto', 'Höchster Puls', 'Pouls le plus haut', 'Pulso mais alto')
_tr7('metric.max.short', '今日アプリが記録した最も高い心拍。', '应用今天记录到的最高心率。', 'Самый высокий пульс, который приложение записало сегодня.', 'El pulso más alto que la app ha registrado hoy.', 'Der höchste Puls, den die App heute aufgezeichnet hat.', 'Le pouls le plus haut que l’app a enregistré aujourd’hui.', 'O pulso mais alto que o app registou hoje.')
_tr7('metric.max.more', '単発のピークはそれ自体ではあまり語らない — もっと大事なのは、そのあとどれだけ速く心拍が戻ったか（HRR）。', '单个峰值本身说明不了什么 — 更重要的是之后心率回落得多快（HRR）。', 'Один скачок сам по себе мало что говорит — важнее, как быстро пульс потом вернулся вниз (HRR).', 'Un pico aislado dice poco por sí solo: importa más lo rápido que bajó el pulso después (HRR).', 'Ein einzelner Ausschlag sagt für sich wenig — wichtiger ist, wie schnell der Puls danach wieder gefallen ist (HRR).', 'Un pic isolé dit peu en soi — ce qui compte davantage, c’est la vitesse à laquelle le pouls est redescendu ensuite (HRR).', 'Um pico isolado diz pouco por si — importa mais a rapidez com que o pulso desceu depois (HRR).')
_tr7('metric.peak.title', '負荷のピーク', '负荷峰值', 'Пик нагрузки', 'Pico de carga', 'Last-Spitze', 'Pic de charge', 'Pico de carga')
_tr7('metric.peak.short', '今日のセッション中の最高の負荷値（0〜100）。', '今天记录中的最高负荷值（0–100）。', 'Самое высокое значение нагрузки (0–100) за сегодняшнюю сессию.', 'El valor de carga más alto (0–100) durante la sesión de hoy.', 'Der höchste Lastwert (0–100) in der heutigen Sitzung.', 'La valeur de charge la plus haute (0–100) pendant la séance du jour.', 'O valor de carga mais alto (0–100) durante a sessão de hoje.')
_tr7('metric.peak.more', '負荷は心拍から三つを組み合わせる：安静時からどれだけ上か、どれだけ速く上がっているか、どれだけ長く高いままか。負荷のピークは、その組み合わせが最も高かった一瞬。', '负荷把心率的三件事合起来：比静息高多少、上升多快、在高位停留多久。负荷峰值就是这个组合最高的那一刻。', 'Нагрузка соединяет три вещи из пульса: насколько ты выше покоя, как быстро он растёт и как долго держится. Пик нагрузки — самый высокий момент этого сочетания.', 'La carga combina tres cosas del pulso: cuánto estás por encima del reposo, con qué rapidez sube y cuánto se mantiene. El pico de carga es el momento más alto de esa combinación.', 'Die Last kombiniert drei Dinge aus dem Puls: wie weit über der Ruhe du bist, wie schnell er steigt und wie lange er oben bleibt. Die Last-Spitze ist der höchste Moment dieser Kombination.', 'La charge combine trois éléments du pouls : de combien tu es au-dessus du repos, à quelle vitesse il monte et combien de temps il reste haut. Le pic de charge est le moment le plus haut de cette combinaison.', 'A carga combina três coisas do pulso: quanto você está acima do repouso, com que rapidez sobe e quanto tempo fica alto. O pico de carga é o momento mais alto dessa combinação.')
_tr7('metric.week.title', '今週のセッション', '本周记录数', 'Сессии на этой неделе', 'Sesiones esta semana', 'Sitzungen diese Woche', 'Séances cette semaine', 'Sessões esta semana')
_tr7('insight.need_more', 'これまで {n}/{need} セッション — 3回そろうと、アプリはそれらを横断して傾向を探しはじめる。', '目前 {n}/{need} 次记录 — 满三次后，应用会开始跨记录寻找规律。', 'Пока {n} из {need} сессий — после трёх приложение начнёт искать закономерности между ними.', 'Por ahora {n} de {need} sesiones: a partir de tres, la app empieza a buscar patrones entre ellas.', 'Bisher {n} von {need} Sitzungen — ab drei sucht die App nach Mustern über sie hinweg.', 'Pour l’instant {n} séances sur {need} — à partir de trois, l’app commence à chercher des tendances.', 'Até agora {n} de {need} sessões — a partir de três, o app começa a procurar padrões entre elas.')
_tr7('log.audio_reset', 'サウンドを推奨値に戻した', '声音已恢复为推荐值', 'Звук возвращён к рекомендуемым значениям', 'Sonido restaurado a los valores recomendados', 'Ton auf empfohlene Werte zurückgesetzt', 'Son remis aux valeurs recommandées', 'Som restaurado para os valores recomendados')
_tr7('log.sessions_exported', 'エクスポート：{n} セッションを表に', '导出：{n} 次记录到表格', 'Экспорт: {n} сессий в таблицу', 'Exportación: {n} sesiones a una hoja de cálculo', 'Export: {n} Sitzungen in eine Tabelle', 'Export : {n} séances vers un tableur', 'Exportação: {n} sessões para uma planilha')
_tr7('log.slots_removed_bulk', '{n} 個のトリガーを削除した。', '已删除 {n} 个触发器。', 'Удалено триггеров: {n}.', 'Se eliminaron {n} disparadores.', '{n} Trigger entfernt.', '{n} déclencheurs supprimés.', 'Removidos {n} gatilhos.')
_tr7('log.hotkey_on', 'ショートカット {combo} が有効 — 30分間静かにします', '快捷键 {combo} 已就绪 — 会让我安静半小时', 'Сочетание {combo} готово — заглушит меня на полчаса', 'El atajo {combo} está listo: me silenciará media hora', 'Tastenkürzel {combo} ist bereit — es macht mich eine halbe Stunde still', 'Le raccourci {combo} est prêt — il me fera taire une demi-heure', 'O atalho {combo} está pronto — me silencia por meia hora')
_tr7('log.snooze_ended', 'ミュートが終わった', '静音结束', 'Пауза закончилась', 'La pausa terminó', 'Pause beendet', 'Pause terminée', 'A pausa terminou')
_tr7('log.snooze_cancelled', 'ミュートを解除した', '已取消静音', 'Пауза отменена', 'Pausa cancelada', 'Pause abgebrochen', 'Pause annulée', 'Pausa cancelada')
_tr7('log.hr_session_saved', 'セッションを保存 — 平均 {avg} BPM、最高 {max} BPM、負荷ピーク {peak}。', '记录已保存 — 平均 {avg} BPM，最高 {max} BPM，负荷峰值 {peak}。', 'Сессия сохранена — средний {avg} уд/мин, пик {max} уд/мин, пик нагрузки {peak}.', 'Sesión guardada: media {avg} ppm, pico {max} ppm, pico de carga {peak}.', 'Sitzung gespeichert — Schnitt {avg} S/min, Spitze {max} S/min, Last-Spitze {peak}.', 'Séance enregistrée — moyenne {avg} bpm, pic {max} bpm, pic de charge {peak}.', 'Sessão salva — média {avg} bpm, pico {max} bpm, pico de carga {peak}.')
_tr7('log.monitor_target', 'ビジュアルと HUD は今後こちらに描画：{target}。', '视觉效果和 HUD 现在绘制在：{target}。', 'Визуалы и HUD теперь рисуются на: {target}.', 'Los visuales y el HUD se dibujarán ahora en: {target}.', 'Visuals und HUD werden jetzt gezeichnet auf: {target}.', 'Les visuels et le HUD se dessineront désormais sur : {target}.', 'Os visuais e o HUD passam a ser desenhados em: {target}.')
_tr7('guide.block.physiology', '体で起きていること', '身体里发生了什么', 'Что происходит в теле', 'Qué pasa en tu cuerpo', 'Was im Körper passiert', 'Ce qui se passe dans le corps', 'O que acontece no corpo')
_tr7('guide.block.instruction', 'あなたがすること', '你要做什么', 'Что делаешь ты', 'Qué haces tú', 'Was du tust', 'Ce que tu fais', 'O que você faz')
_tr7('guide.not_medical_note',
     'これは健康のための一般的なヒントで、医学的な助言ではありません — Zanshin は医療機器ではありません。心臓や呼吸に問題があるなら、まず医師に相談してください。',
     '这些是一般性的健康小贴士，不是医疗建议 — Zanshin 不是医疗器械。如果你有心脏或呼吸方面的问题，请先咨询医生。',
     'Это общие советы для самочувствия, а не медицинская рекомендация — Zanshin не является медицинским изделием. Если у тебя проблемы с сердцем или дыханием, сначала посоветуйся с врачом.',
     'Son consejos generales de bienestar, no consejo médico — Zanshin no es un producto sanitario. Si tienes algún problema de corazón o de respiración, consulta antes con un médico.',
     'Das sind allgemeine Tipps fürs Wohlbefinden, kein medizinischer Rat — Zanshin ist kein Medizinprodukt. Wenn du Herz- oder Atembeschwerden hast, sprich zuerst mit einer Ärztin oder einem Arzt.',
     "Ce sont des conseils généraux de bien-être, pas un avis médical — Zanshin n'est pas un dispositif médical. Si tu as un problème cardiaque ou respiratoire, parles-en d'abord à un médecin.",
     'São dicas gerais de bem-estar, não aconselhamento médico — o Zanshin não é um dispositivo médico. Se você tem algum problema cardíaco ou respiratório, fale primeiro com um médico.')
_tr7('hud.section_title', 'ゲーム中の心拍パネル', '游戏中的心率面板', 'Панель пульса в игре', 'Panel de pulso en el juego', 'Puls-Panel im Spiel', 'Panneau de pouls en jeu', 'Painel de pulso no jogo')
_tr7('hud.enable', 'ゲーム中にパネルを表示 — 配信向け', '在游戏中显示面板 — 用于直播', 'Показывать панель в игре — для стрима', 'Mostrar el panel en el juego — para streaming', 'Panel im Spiel zeigen — fürs Streaming', 'Afficher le panneau en jeu — pour le stream', 'Mostrar o painel no jogo — para stream')
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
_tr7('hud.session.triggers', 'リマインダー {n}', '提醒 {n}', 'НАПОМИНАНИЙ {n}', 'RECORDATORIOS {n}', 'ERINNERUNGEN {n}', 'RAPPELS {n}', 'LEMBRETES {n}')
_tr7('hud.session.over', 'しきい値超え {time}', '超阈 {time}', 'ВЫШЕ ПОРОГА {time}', 'SOBRE EL LÍMITE {time}', 'ÜBER DER GRENZE {time}', 'AU-DESSUS DU SEUIL {time}', 'ACIMA DO LIMITE {time}')
_tr7('hud.trigger_row.title', 'ゲーム中の機能アイコン', '游戏中的功能图标', 'Значки функций в игре', 'Iconos de funciones en el juego', 'Funktionssymbole im Spiel', 'Icônes de fonctions en jeu', 'Ícones de funções no jogo')
_tr7('hud.trigger_row.toggle', 'ゲーム中にアイコンを表示', '在游戏中显示图标', 'Показывать значки в игре', 'Mostrar iconos en el juego', 'Symbole im Spiel zeigen', 'Afficher les icônes en jeu', 'Mostrar ícones no jogo')
_tr7('hud.trigger_row.color', 'アイコンの色', '图标颜色', 'Цвет значков', 'Color de los iconos', 'Symbolfarbe', 'Couleur des icônes', 'Cor dos ícones')
_tr7('hud.trigger_row.color_theme', 'テーマの色', '主题色', 'Цвет темы', 'Color del tema', 'Themenfarbe', 'Couleur du thème', 'Cor do tema')
_tr7('hud.snooze.5min', '5 分', '5 分钟', '5 минут', '5 minutos', '5 Minuten', '5 minutes', '5 minutos')
_tr7('hud.snooze.20min', '20 分', '20 分钟', '20 минут', '20 minutos', '20 Minuten', '20 minutes', '20 minutos')
_tr7('hud.snooze.40min', '40 分', '40 分钟', '40 минут', '40 minutos', '40 Minuten', '40 minutes', '40 minutos')
_tr7('hud.snooze.60min', '60 分', '60 分钟', '60 минут', '60 minutos', '60 Minuten', '60 minutes', '60 minutos')
_tr7('hud.snooze.cancel', 'ミュートを解除', '取消静音', 'Отменить паузу', 'Cancelar la pausa', 'Pause aufheben', 'Annuler la pause', 'Cancelar a pausa')
_tr7('overlay.dialog_title', 'ゲーム中のビジュアル', '游戏中的视觉效果', 'Визуалы в игре', 'Visuales en el juego', 'Visuals im Spiel', 'Visuels en jeu', 'Visuais no jogo')
_tr7('overlay.caption.grounding', '重心を落として', '沉下重心', 'ОПУСТИ ЦЕНТР ТЯЖЕСТИ', 'BAJA EL PESO', 'GEWICHT SENKEN', 'RELÂCHE TON POIDS', 'BAIXA O PESO')
_tr7('overlay.caption.jaw', '顎をゆるめて', '松开下巴', 'РАЗОЖМИ ЧЕЛЮСТЬ', 'AFLOJA LA MANDÍBULA', 'KIEFER LOCKERN', 'DESSERRE LA MÂCHOIRE', 'SOLTA O MAXILAR')
_tr7('overlay.caption.release', '握りをゆるめて', '松开握力', 'ОСЛАБЬ ХВАТ', 'AFLOJA LA MANO', 'GRIFF LOCKERN', 'RELÂCHE TA PRISE', 'SOLTA A MÃO')
_tr7('overlay.caption.inhale', '吸って', '吸气', 'ВДОХ', 'INSPIRA', 'EINATMEN', 'INSPIRE', 'INSPIRA')
_tr7('overlay.caption.exhale', '吐いて', '呼气', 'ВЫДОХ', 'ESPIRA', 'AUSATMEN', 'EXPIRE', 'EXPIRA')
_tr7('overlay.monitor.label', 'どの画面に描くか', '在哪块屏幕上绘制', 'На каком экране рисовать', 'En qué pantalla dibujar', 'Auf welchem Bildschirm zeichnen', 'Sur quel écran dessiner', 'Em qual tela desenhar')
_tr7('overlay.monitor.pick', '画面', '屏幕', 'Экран', 'Pantalla', 'Bildschirm', 'Écran', 'Tela')
_tr7('overlay.monitor.auto', '自動（ゲームが動いている画面）', '自动（游戏所在的屏幕）', 'Автоматически (где идёт игра)', 'Automático (donde corre el juego)', 'Automatisch (wo das Spiel läuft)', 'Automatique (où tourne le jeu)', 'Automático (onde o jogo está rodando)')
_tr7('overlay.monitor.cursor', 'カーソルのある画面', '光标所在的屏幕', 'Где курсор', 'Donde está el cursor', 'Wo der Cursor ist', 'Où est le curseur', 'Onde está o cursor')
_tr7('overlay.monitor.primary', 'メインモニター', '主显示器', 'Основной монитор', 'Monitor principal', 'Hauptmonitor', 'Moniteur principal', 'Monitor principal')
_tr7('overlay.monitor.hint', '「自動」ならアプリはアクティブなウィンドウのある画面 — つまり今プレイしている画面 — に描く。', '选“自动”时，应用会画在当前活动窗口所在的屏幕上 — 也就是你正在玩的那块。', 'При «Автоматически» приложение рисует на том экране, где активное окно, — то есть на том, где ты играешь.', 'Con «Automático» la app dibuja en la pantalla que tiene la ventana activa, es decir, en la que estás jugando.', 'Bei „Automatisch“ zeichnet die App auf dem Bildschirm mit dem aktiven Fenster — also dem, auf dem du spielst.', 'Avec « Automatique », l’app dessine sur l’écran qui a la fenêtre active — celui sur lequel tu joues.', 'Com “Automático”, o app desenha na tela que tem a janela ativa — aquela em que você está jogando.')
_tr7('overlay.fine_tune', 'サイズと位置を微調整…', '微调大小和位置…', 'Точная настройка размера и положения…', 'Ajustar tamaño y posición…', 'Größe und Position feinjustieren…', 'Ajuster finement taille et position…', 'Ajustar tamanho e posição…')
_tr7('overlay.test_done', '完了', '完成', 'Готово', 'Listo', 'Fertig', 'Terminé', 'Pronto')
_tr7('overlay.drag_hint', '「テスト」を押すとアイコンが画面に出る — マウスでつかんで好きな場所へドラッグ。もう一度クリックすると位置が保存される。', '点击“测试”，图标会出现在屏幕上 — 用鼠标抓住拖到你想要的位置。再点一次即可保存位置。', 'Нажми «Тест» — значок появится на экране; хватай мышью и тащи куда хочешь. Ещё один клик сохранит положение.', 'Pulsa «Probar» y el icono aparece en pantalla: agárralo con el ratón y arrástralo donde quieras. Otro clic guarda la posición.', 'Klick auf „Test“ und das Symbol erscheint auf dem Bildschirm — pack es mit der Maus und zieh es, wohin du willst. Ein weiterer Klick speichert die Position.', 'Clique sur « Test » et l’icône apparaît à l’écran — attrape-la à la souris et place-la où tu veux. Un autre clic enregistre la position.', 'Clique em “Testar” e o ícone aparece na tela — pegue-o com o mouse e arraste para onde quiser. Outro clique salva a posição.')
_tr7('overlay.color_title', 'アイコンの色', '图标颜色', 'Цвет значка', 'Color del icono', 'Symbolfarbe', 'Couleur de l’icône', 'Cor do ícone')
_tr7('overlay.breath_seconds', '呼吸のサイクル（秒）', '呼吸周期（秒）', 'Цикл дыхания (в секундах)', 'Ciclo de respiración (en segundos)', 'Atemzyklus (in Sekunden)', 'Cycle de respiration (en secondes)', 'Ciclo de respiração (em segundos)')
_tr7('overlay.breath_inhale', '吸う長さ（秒）', '吸气时长（秒）', 'Длина вдоха (с)', 'Duración de la inspiración (s)', 'Länge des Einatmens (s)', 'Durée de l’inspiration (s)', 'Duração da inspiração (s)')
_tr7('overlay.breath_exhale', '吐く長さ（秒）', '呼气时长（秒）', 'Длина выдоха (с)', 'Duración de la espiración (s)', 'Länge des Ausatmens (s)', 'Durée de l’expiration (s)', 'Duração da expiração (s)')
_tr7('hr.pair_button', '時計のつなぎ方…', '如何连接手表…', 'Как подключить часы…', 'Cómo vincular tu reloj…', 'Uhr verbinden…', 'Comment connecter ta montre…', 'Como parear o seu relógio…')
_tr7('hr.pair_title', '時計をつなぐ', '连接你的手表', 'Подключение часов', 'Vincular tu reloj', 'Uhr verbinden', 'Connecter ta montre', 'Parear o seu relógio')
_tr7('hr.pair_intro', 'アプリは OBS のふりをする — 電話が「HeartRateOnStream for OBS」経由で心拍を送る。一度設定すれば、あとは勝手に動く。', '应用会伪装成 OBS — 手机通过 “HeartRateOnStream for OBS” 把心率发过来。设置一次，之后就自动运行。', 'Приложение притворяется OBS — телефон шлёт пульс через приложение «HeartRateOnStream for OBS». Настроишь один раз, дальше работает само.', 'La app se hace pasar por OBS: tu móvil envía el pulso a través de «HeartRateOnStream for OBS». Lo configuras una vez y ya funciona solo.', 'Die App gibt sich als OBS aus — dein Handy sendet den Puls über die App „HeartRateOnStream for OBS“. Einmal einrichten, dann läuft es von selbst.', 'L’app se fait passer pour OBS — ton téléphone envoie le pouls via l’app « HeartRateOnStream for OBS ». Tu configures une fois, ensuite ça tourne tout seul.', 'O app se passa pelo OBS — o celular envia o pulso pelo app “HeartRateOnStream for OBS”. Você configura uma vez, e depois funciona por conta própria.')
_tr7('hr.pair_this_pc', 'この PC のアドレスとポート — 電話に入力する', '这台电脑的地址和端口 — 输入到手机里', 'АДРЕС И ПОРТ ЭТОГО ПК — введи их в телефоне', 'DIRECCIÓN Y PUERTO DE ESTE PC: escríbelos en el móvil', 'ADRESSE UND PORT DIESES PCS — im Handy eintragen', 'ADRESSE ET PORT DE CE PC — à saisir sur le téléphone', 'ENDEREÇO E PORTA DESTE PC — digite-os no celular')
_tr7('hr.pair_ip_unknown', 'IP を検出できなかった', '无法检测到 IP', 'Не удалось определить IP', 'No se pudo detectar la IP', 'IP konnte nicht erkannt werden', 'Impossible de détecter l’IP', 'Não foi possível detectar o IP')
_tr7('hr.pair_ip_help', 'コマンドプロンプトを開いて ipconfig と入力 — 「IPv4 アドレス」を探す（たいてい 192.168.x.x）。電話と PC は同じ Wi‑Fi にいる必要がある。', '打开命令提示符输入 ipconfig — 找到 “IPv4 地址”（通常是 192.168.x.x）。手机和电脑必须在同一个 Wi‑Fi 上。', 'Открой командную строку и набери ipconfig — найди «IPv4-адрес» (обычно 192.168.x.x). Телефон и ПК должны быть в одном Wi‑Fi.', 'Abre el símbolo del sistema y escribe ipconfig: busca «Dirección IPv4» (suele ser 192.168.x.x). El móvil y el PC deben estar en el mismo Wi‑Fi.', 'Öffne die Eingabeaufforderung und tippe ipconfig — such nach „IPv4-Adresse“ (meist 192.168.x.x). Handy und PC müssen im selben WLAN sein.', 'Ouvre l’invite de commandes et tape ipconfig — cherche « Adresse IPv4 » (souvent 192.168.x.x). Le téléphone et le PC doivent être sur le même Wi‑Fi.', 'Abra o Prompt de Comando e digite ipconfig — procure “Endereço IPv4” (normalmente 192.168.x.x). O celular e o PC precisam estar no mesmo Wi‑Fi.')
_tr7('hr.pair_other_ips', 'この PC の他のアドレス（最初のが効かない場合）：{ips}', '这台电脑的其他地址（如果第一个不行）：{ips}', 'Другие адреса этого ПК (если первый не работает): {ips}', 'Otras direcciones de este PC (si la primera no funciona): {ips}', 'Weitere Adressen dieses PCs (falls die erste nicht geht): {ips}', 'Autres adresses de ce PC (si la première ne marche pas) : {ips}', 'Outros endereços deste PC (se o primeiro não funcionar): {ips}')
_tr7('hr.pair_ip_note', '設定では 0.0.0.0 のままにする — この番号は電話に入れるためだけのもの。', '设置里保持 0.0.0.0 — 这个号码只用来填进手机。', 'В настройках оставь 0.0.0.0 — это число идёт только в телефон.', 'Deja 0.0.0.0 en los ajustes: este número solo se escribe en el móvil.', 'Lass in den Einstellungen 0.0.0.0 — diese Zahl kommt nur ins Handy.', 'Laisse 0.0.0.0 dans les réglages — ce numéro ne sert qu’au téléphone.', 'Deixe 0.0.0.0 nas configurações — este número vai só para o celular.')
_tr7('hr.step1_title', '同じ Wi‑Fi', '同一个 Wi‑Fi', 'Один Wi‑Fi', 'El mismo Wi‑Fi', 'Dasselbe WLAN', 'Le même Wi‑Fi', 'O mesmo Wi‑Fi')
_tr7('hr.step1_body', '時計とつながった電話と、この PC が同じ Wi‑Fi にいること（モバイル通信ではない）。', '连着手表的手机和这台电脑要在同一个 Wi‑Fi 上（不是移动数据）。', 'Телефон с часами и этот ПК — в одном Wi‑Fi (не в мобильном интернете).', 'El móvil con el reloj y este PC en el mismo Wi‑Fi (no datos móviles).', 'Handy mit der Uhr und dieser PC im selben WLAN (nicht mobile Daten).', 'Le téléphone avec la montre et ce PC sur le même Wi‑Fi (pas en données mobiles).', 'O celular com o relógio e este PC no mesmo Wi‑Fi (não nos dados móveis).')
_tr7('hr.step2_title', '電話にアプリを入れる', '安装手机应用', 'Установи приложение на телефон', 'Instala la app del móvil', 'Handy-App installieren', 'Installe l’app du téléphone', 'Instale o app no celular')
_tr7('hr.step3_title', 'アドレスとポートを入れる', '输入地址和端口', 'Введи адрес и порт', 'Escribe la dirección y el puerto', 'Adresse und Port eintragen', 'Saisis l’adresse et le port', 'Digite o endereço e a porta')
_tr7('hr.step3_body', '電話のアプリに、上の枠のアドレスとポートを入力する。パスワードは空のままでいい。', '在手机应用里填入上方框里的地址和端口。密码留空。', 'В приложении на телефоне введи адрес и порт из рамки выше. Пароль оставь пустым.', 'En la app del móvil introduce la dirección y el puerto del recuadro de arriba. Deja la contraseña vacía.', 'Trag in der Handy-App die Adresse und den Port aus dem Feld oben ein. Das Passwort bleibt leer.', 'Dans l’app du téléphone, saisis l’adresse et le port du cadre ci-dessus. Laisse le mot de passe vide.', 'No app do celular, digite o endereço e a porta do quadro acima. Deixe a senha em branco.')
_tr7('hr.step4_title', 'シーンとソースを選ぶ', '选择场景和来源', 'Выбери сцену и источник', 'Elige la escena y la fuente', 'Szene und Quelle wählen', 'Choisis la scène et la source', 'Escolha a cena e a fonte')
_tr7('hr.step4_body', 'つながったら、シーン「Zanshin」とソース「Tep」を選ぶ。歩数と速度も送れるなら、ソース「Kroky」と「Rychlost」もある。', '连接之后，选择场景 “Zanshin” 和来源 “Tep”。如果还能发送步数和速度，那里也有来源 “Kroky” 和 “Rychlost”。', 'После подключения выбери сцену «Zanshin» и источник «Tep». Если можешь отправлять ещё шаги и скорость, там есть и источники «Kroky» и «Rychlost».', 'Una vez conectado, elige la escena «Zanshin» y la fuente «Tep». Si también puedes enviar pasos y velocidad, ahí están además las fuentes «Kroky» y «Rychlost».', 'Sobald verbunden, wähle die Szene „Zanshin“ und die Quelle „Tep“. Wenn du auch Schritte und Tempo senden kannst, gibt es dort außerdem die Quellen „Kroky“ und „Rychlost“.', 'Une fois connecté, choisis la scène « Zanshin » et la source « Tep ». Si tu peux aussi envoyer les pas et la vitesse, les sources « Kroky » et « Rychlost » sont là aussi.', 'Depois de conectado, escolha a cena “Zanshin” e a fonte “Tep”. Se você também puder enviar passos e velocidade, as fontes “Kroky” e “Rychlost” também estão lá.')
_tr7('hr.step5_title', 'ここでセンサーを入れる', '在这里打开传感器', 'Включи датчик здесь', 'Activa el sensor aquí', 'Sensor hier einschalten', 'Active le capteur ici', 'Ative o sensor aqui')
_tr7('hr.step5_body', 'ここに戻って「時計から心拍を受け取る」を入れる。数秒で見えるはず。', '回到这里，打开“接收手表的心率”。几秒内就能看到。', 'Вернись сюда и включи «Слушать пульс с часов». Увидишь его через пару секунд.', 'Vuelve aquí y activa «Escuchar el pulso del reloj». Lo verás en unos segundos.', 'Komm hierher zurück und schalte „Puls von der Uhr empfangen“ ein. Du siehst ihn in Sekunden.', 'Reviens ici et active « Écouter le pouls de la montre ». Tu le verras en quelques secondes.', 'Volte aqui e ative “Ouvir o pulso do relógio”. Você vai vê-lo em segundos.')
_tr7('hr.trouble_title', '時計はつながるのに心拍が来ない？', '手表连上了却没有心率？', 'Часы подключаются, а пульса нет?', '¿El reloj conecta pero no llega el pulso?', 'Uhr verbindet sich, aber kein Puls?', 'La montre se connecte mais pas de pouls ?', 'O relógio conecta, mas o pulso não chega?')
_tr7('hr.trouble_body', '電話側でシーン「Zanshin」とソース「Tep」を確認し、時計が実際に測っているかも見て。初回起動時、Windows はアプリにネットワークを許可するか尋ねる — 拒否していたら時計はつながらない（ファイアウォールで許可して）。別のプログラムがポートを取っているなら、ここと電話の両方で番号を変える。', '检查手机上的场景 “Zanshin” 和来源 “Tep”，并确认手表确实在测量。首次运行时，Windows 会询问是否允许应用访问网络——如果你拒绝了，手表就连不上（请在防火墙中允许它）。如果端口被别的程序占用，就在这里和手机上一起改。', 'Проверь на телефоне сцену «Zanshin» и источник «Tep», а также что часы действительно измеряют. При первом запуске Windows спрашивает, пускать ли приложение в сеть, — если ты отказал, часы не подключатся (разреши его в брандмауэре). Если порт занят другой программой, поменяй его здесь и в телефоне.', 'Comprueba en el móvil la escena «Zanshin» y la fuente «Tep», y que el reloj esté midiendo de verdad. La primera vez, Windows pregunta si permitir la app en la red: si lo rechazaste, el reloj no puede conectarse (permítela en el firewall). Si otro programa ocupó el puerto, cámbialo aquí y en el móvil.', 'Prüfe am Handy die Szene „Zanshin“ und die Quelle „Tep“ und ob die Uhr wirklich misst. Beim ersten Start fragt Windows, ob die App ins Netzwerk darf — wenn du abgelehnt hast, kann sich die Uhr nicht verbinden (erlaube sie in der Firewall). Wenn ein anderes Programm den Port belegt, ändere ihn hier und am Handy.', 'Vérifie sur le téléphone la scène « Zanshin » et la source « Tep », et que la montre mesure vraiment. Au premier lancement, Windows demande s’il faut autoriser l’app sur le réseau — si tu as refusé, la montre ne peut pas se connecter (autorise-la dans le pare-feu). Si un autre programme a pris le port, change-le ici et sur le téléphone.', 'Verifique no celular a cena “Zanshin” e a fonte “Tep”, e se o relógio está medindo de verdade. Na primeira execução, o Windows pergunta se deve liberar o app na rede — se você recusou, o relógio não consegue se conectar (libere-o no firewall). Se outro programa ocupou a porta, mude-a aqui e no celular.')
_tr7('hr.qr_show', '電話で読み取る', '用手机扫描', 'Отсканировать телефоном', 'Escanear con el móvil', 'Mit dem Handy scannen', 'Scanner avec le téléphone', 'Ler com o celular')
_tr7('hr.qr_hide', 'コードを隠す', '隐藏二维码', 'Скрыть коды', 'Ocultar los códigos', 'Codes ausblenden', 'Masquer les codes', 'Esconder os códigos')
_tr7('hr.qr_android', 'Android / Wear OS\n「HeartRateOnStream for OBS」（無料）。\nこの PC の IP とポートをその中で設定。', 'Android / Wear OS\n“HeartRateOnStream for OBS”（免费）。\n在里面填上这台电脑的 IP 和端口。', 'Android / Wear OS\n«HeartRateOnStream for OBS» (бесплатно).\nВнутри укажи IP и порт этого ПК.', 'Android / Wear OS\n«HeartRateOnStream for OBS» (gratis).\nDentro pon la IP y el puerto de este PC.', 'Android / Wear OS\n„HeartRateOnStream for OBS“ (kostenlos).\nDarin IP und Port dieses PCs eintragen.', 'Android / Wear OS\n« HeartRateOnStream for OBS » (gratuit).\nY saisir l’IP et le port de ce PC.', 'Android / Wear OS\n“HeartRateOnStream for OBS” (grátis).\nNele, defina o IP e a porta deste PC.')
_tr7('hr.qr_note', 'どちらも他社のアプリで、うちのものではない — こちらはただ受け取れるだけ。', '这两个都是别人的应用，不是我们的 — 我们只是能接收它们。', 'Оба приложения чужие, не наши — мы просто умеем их слушать.', 'Ambas apps son de otros, no nuestras: nosotros solo sabemos escucharlas.', 'Beide Apps gehören anderen, nicht uns — wir können ihnen nur zuhören.', 'Les deux apps appartiennent à d’autres, pas à nous — on sait juste les écouter.', 'Os dois apps são de terceiros, não nossos — nós só sabemos ouvi-los.')
_tr7('settings.title', 'サウンドと音声', '声音与语音', 'Звук и голос', 'Sonido y voz', 'Ton und Stimme', 'Son et voix', 'Som e voz')
_tr7('settings.auto_profile_unavailable', 'ゲームによる自動切り替えは今は使えない（psutil ライブラリがない）', '目前无法按游戏自动切换（缺少 psutil 库）', 'Автопереключение по игре сейчас недоступно (нет библиотеки psutil)', 'El cambio automático por juego no está disponible ahora (falta la librería psutil)', 'Automatischer Wechsel nach Spiel ist gerade nicht verfügbar (Bibliothek psutil fehlt)', 'Le changement automatique par jeu n’est pas disponible (bibliothèque psutil manquante)', 'A troca automática por jogo não está disponível agora (falta a biblioteca psutil)')
_tr7('settings.overlay_button', '🎮 ゲーム中のビジュアル…', '🎮 游戏中的视觉效果…', '🎮 Визуалы в игре…', '🎮 Visuales en el juego…', '🎮 Visuals im Spiel…', '🎮 Visuels en jeu…', '🎮 Visuais no jogo…')
_tr7('settings.strict_global_lock', '一度にリマインダーは一つ', '同一时间只有一个提醒', 'Одно напоминание за раз', 'Un recordatorio a la vez', 'Eine Erinnerung auf einmal', 'Un rappel à la fois', 'Um lembrete de cada vez')
_tr7('settings.strict_global_lock_short', '一度にリマインダーは一つ', '同一时间只有一个提醒', 'Одно напоминание за раз', 'Un recordatorio a la vez', 'Eine Erinnerung auf einmal', 'Un rappel à la fois', 'Um lembrete de cada vez')
_tr7('settings.strict_global_lock_sub', '一つが鳴っているあいだ、他は黙る — でないと激しい撃ち合いで重なってしまう。', '一个在播放时其他保持安静 — 否则激烈交火时会叠在一起。', 'Пока играет одно, остальные молчат — иначе в плотной перестрелке они наложатся.', 'Mientras suena uno, los demás callan; de lo contrario se solapan en un tiroteo intenso.', 'Während eine läuft, schweigen die anderen — sonst überlagern sie sich im hitzigen Gefecht.', 'Pendant qu’un joue, les autres se taisent — sinon ils se chevauchent dans une fusillade dense.', 'Enquanto um toca, os outros ficam em silêncio — senão eles se sobrepõem num tiroteio intenso.')
_tr7('settings.hr_section_title', '時計と心拍', '手表与心率', 'Часы и пульс', 'Reloj y pulso', 'Uhr und Puls', 'Montre et pouls', 'Relógio e pulso')
_tr7('settings.hr_ip_hint', '0.0.0.0 のままでいい（すべてで待ち受ける） — 迷ったら下の「時計のつなぎ方」を見て。', '保持 0.0.0.0（在所有网卡上监听）— 不确定就看下面的“如何连接手表”。', 'Оставь 0.0.0.0 (слушает везде) — не уверен? Смотри «Как подключить часы» ниже.', 'Deja 0.0.0.0 (escucha en todas partes); ¿no estás seguro? Mira «Cómo vincular tu reloj» abajo.', 'Lass 0.0.0.0 (lauscht überall) — unsicher? Siehe unten „Uhr verbinden“.', 'Laisse 0.0.0.0 (écoute partout) — pas sûr ? Vois « Comment connecter ta montre » ci-dessous.', 'Deixe 0.0.0.0 (escuta em todo lugar) — na dúvida, veja “Como parear o seu relógio” abaixo.')
_tr7('settings.hr_port_hint', '分からなければ 4455 のまま — 時計のアプリにも同じ番号が必要。', '不清楚就保持 4455 — 手表应用里也要填同一个号码。', 'Оставь 4455, если не знаешь лучше — в приложении часов нужен тот же номер.', 'Deja 4455 salvo que sepas otra cosa: la app del reloj necesita el mismo número.', 'Lass 4455, wenn du es nicht besser weißt — die Uhr-App braucht dieselbe Nummer.', 'Laisse 4455 sauf si tu sais mieux — l’app de la montre a besoin du même numéro.', 'Deixe 4455, a não ser que você saiba o que está fazendo — o app do relógio precisa do mesmo número.')
_tr7('settings.hr_enable_switch', '時計から心拍を受け取る', '接收手表的心率', 'Слушать пульс с часов', 'Escuchar el pulso del reloj', 'Puls von der Uhr empfangen', 'Écouter le pouls de la montre', 'Ouvir o pulso do relógio')
_tr7('settings.cooldown', 'リマインダーの間隔', '提醒之间的间隔', 'Пауза между напоминаниями', 'Pausa entre recordatorios', 'Pause zwischen Erinnerungen', 'Pause entre les rappels', 'Pausa entre lembretes')
_tr7('settings.cooldown_sub', 'アプリがまた話すまでの最短時間。短ければ頻繁に、長ければゲームに集中させてくれる。', '应用再次开口前的最短时间。间隔短会经常提醒，长则让你安心玩。', 'Кратчайшее время, прежде чем приложение заговорит снова. Короткая пауза напоминает часто, длинная даёт спокойно играть.', 'El tiempo mínimo antes de que la app vuelva a hablar. Una pausa corta recuerda a menudo; una larga te deja jugar.', 'Die kürzeste Zeit, bis die App wieder spricht. Eine kurze Pause erinnert oft, eine lange lässt dich spielen.', 'Le temps minimum avant que l’app reparle. Une pause courte rappelle souvent, une longue te laisse jouer.', 'O tempo mínimo antes de o app falar de novo. Uma pausa curta lembra muitas vezes; uma longa te deixa jogar.')
_tr7('settings.volume', '音量', '音量', 'Громкость', 'Volumen', 'Lautstärke', 'Volume', 'Volume')
_tr7('settings.volume_sub', 'リマインダーだけに効く。ゲームの音量は変わらない。', '只影响提醒。不会改变游戏音量。', 'Действует только на напоминания. Громкость игры не меняется.', 'Solo afecta a los recordatorios. No cambia el volumen del juego.', 'Gilt nur für die Erinnerungen. Die Spiellautstärke ändert sich nicht.', 'Ne concerne que les rappels. Ne change pas le volume du jeu.', 'Só se aplica aos lembretes. Não muda o volume do jogo.')
_tr7('settings.balance', '効果音 ↔ 音声のバランス', '音效 ↔ 语音 比例', 'Баланс звук ↔ голос', 'Mezcla sonido ↔ voz', 'Verhältnis Ton ↔ Stimme', 'Équilibre son ↔ voix', 'Mistura som ↔ voz')
_tr7('settings.balance_sub', '音量を効果音と話し声にどう配分するか。左は効果音寄り、右は音声寄り。', '音量在音效和语音之间如何分配。偏左更偏音效，偏右更偏语音。', 'Как громкость делится между звуковым эффектом и голосом. Влево — больше звука, вправо — больше голоса.', 'Cómo se reparte el volumen entre el efecto de sonido y la voz. A la izquierda manda el sonido; a la derecha, la voz.', 'Wie sich die Lautstärke zwischen Soundeffekt und Sprachzeile aufteilt. Links führt der Ton, rechts die Stimme.', 'Comment le volume se répartit entre l’effet sonore et la voix. À gauche le son domine, à droite la voix.', 'Como o volume se divide entre o efeito sonoro e a voz. À esquerda manda o som, à direita a voz.')
_tr7('settings.balance_center', '半々', '各半', 'поровну', 'a partes iguales', 'halb-halb', 'à parts égales', 'meio a meio')
_tr7('settings.balance_sfx', '効果音', '音效', 'звук', 'sonido', 'Ton', 'son', 'som')
_tr7('settings.balance_tts', '音声', '语音', 'голос', 'voz', 'Stimme', 'voix', 'voz')
_tr7('settings.overlap', 'セリフが重なってもよい', '语音可以重叠', 'Реплики могут накладываться', 'Las frases pueden solaparse', 'Sprachzeilen dürfen sich überlappen', 'Les répliques peuvent se chevaucher', 'As frases podem se sobrepor')
_tr7('settings.overlap_sub', 'オフ：セリフは順番待ち。オン：同時に鳴ってよい — トリガーが近くで重なるときに便利。', '关闭：语音会排队。开启：可以同时响 — 当多个触发器挨得很近时很有用。', 'Выключено: реплики ждут друг друга. Включено: могут звучать одновременно — удобно, когда триггеры срабатывают подряд.', 'Apagado: las frases se esperan. Encendido: pueden sonar a la vez, útil cuando varios disparadores caen juntos.', 'Aus: Sprachzeilen warten aufeinander. An: sie können gleichzeitig klingen — praktisch, wenn mehrere Trigger dicht beieinander feuern.', 'Désactivé : les répliques s’attendent. Activé : elles peuvent sonner en même temps — pratique quand plusieurs déclencheurs se suivent.', 'Desligado: as frases esperam umas pelas outras. Ligado: podem soar ao mesmo tempo — útil quando vários gatilhos disparam juntos.')
_tr7('settings.engine', '音声の生成元', '语音来源', 'Голос берётся из', 'La voz viene de', 'Stimme kommt von', 'La voix vient de', 'A voz vem de')
_tr7('settings.engine_sub', '自然な音声のほうがよく聞こえるが、セリフをネット経由で先に用意する必要がある。Windows の音声はいつでもすぐ使える。', '自然语音听起来更好，但需要先通过网络准备好台词。Windows 语音随时可用。', 'Естественный голос звучит лучше, но реплики сперва нужно подготовить через интернет. Голос Windows доступен сразу и всегда.', 'La voz natural suena mejor, pero primero tiene que preparar las frases por internet. La voz de Windows está siempre disponible al instante.', 'Die natürliche Stimme klingt besser, muss die Zeilen aber erst übers Internet vorbereiten. Die Windows-Stimme ist immer sofort da.', 'La voix naturelle sonne mieux mais doit d’abord préparer les répliques via internet. La voix Windows est toujours disponible immédiatement.', 'A voz natural soa melhor, mas tem de preparar as frases pela internet primeiro. A voz do Windows está sempre disponível de imediato.')
_tr7('settings.voice', '音声', '语音', 'Голос', 'Voz', 'Stimme', 'Voix', 'Voz')
_tr7('settings.voice_sub', '自分の音声を持たないすべてのトリガーに使われる。', '用于所有没有设置自己语音的触发器。', 'Используется для каждого триггера, у которого нет своего голоса.', 'Se usa para cada disparador que no tenga voz propia.', 'Wird für jeden Trigger verwendet, der keine eigene Stimme hat.', 'Utilisée pour chaque déclencheur qui n’a pas sa propre voix.', 'Usada para cada gatilho que não tenha voz própria.')
_tr7('settings.rate', '話す速さ', '语速', 'Скорость речи', 'Velocidad del habla', 'Sprechtempo', 'Vitesse de parole', 'Velocidade da fala')
_tr7('settings.rate_sub', 'マイナスで遅く、プラスで速く。ストレス下ではゆっくりのほうが聞き取りやすい。', '负数变慢，正数变快。压力大时慢一点更容易听懂。', 'Минус замедляет, плюс ускоряет. Под стрессом медленную речь легче воспринимать.', 'El menos la ralentiza y el más la acelera. Bajo estrés se sigue mejor un habla más lenta.', 'Minus verlangsamt, Plus beschleunigt. Unter Stress folgt man langsamerer Sprache leichter.', 'Le moins ralentit, le plus accélère. Sous stress, une parole plus lente est plus facile à suivre.', 'O menos deixa mais lenta, o mais acelera. Sob estresse, uma fala mais lenta é mais fácil de acompanhar.')
_tr7('settings.preview', 'どう聞こえるか', '听起来如何', 'Как это звучит', 'Cómo suena', 'Wie es klingt', 'Comment ça sonne', 'Como soa')
_tr7('settings.preview_sub', '最初のリマインダーを、ゲーム中とまったく同じように鳴らす — この音声、この音量、このバランスで。', '按游戏中的原样播放第一条提醒 — 用当前的语音、音量和比例。', 'Проигрывает первое напоминание ровно так, как оно прозвучит в игре — этим голосом, громкостью и балансом.', 'Reproduce el primer recordatorio exactamente como sonará en el juego, con esta voz, volumen y mezcla.', 'Spielt die erste Erinnerung genau so, wie sie im Spiel klingen wird — mit dieser Stimme, Lautstärke und Mischung.', 'Joue le premier rappel exactement comme il sonnera en jeu — avec cette voix, ce volume et cet équilibre.', 'Toca o primeiro lembrete exatamente como soará no jogo — com esta voz, volume e mistura.')
_tr7('settings.preview_btn', '試す', '试听', 'Попробовать', 'Probar', 'Ausprobieren', 'Essayer', 'Experimentar')
_tr7('settings.audio_voice_title', '話されるセリフ', '语音台词', 'Произносимые реплики', 'Frases habladas', 'Gesprochene Zeilen', 'Répliques parlées', 'Frases faladas')
_tr7('settings.audio_volume_title', '音の大きさ', '响度', 'Громкость', 'Volumen', 'Lautstärke', 'Volume sonore', 'Volume')
_tr7('settings.audio_timing_title', 'タイミング', '时机', 'Тайминг', 'Tiempos', 'Timing', 'Rythme', 'Tempo')
_tr7('settings.pace_often', '頻繁', '频繁', 'часто', 'a menudo', 'oft', 'souvent', 'muitas vezes')
_tr7('settings.pace_balanced', 'ほどよく', '均衡', 'сбалансированно', 'equilibrado', 'ausgewogen', 'équilibré', 'equilibrado')
_tr7('settings.pace_rare', 'まれに', '较少', 'редко', 'rara vez', 'selten', 'rarement', 'raramente')
_tr7('settings.speed_slow', 'ゆっくり', '慢', 'медленно', 'lento', 'langsam', 'lent', 'lento')
_tr7('settings.speed_normal', 'ふつう', '正常', 'нормально', 'normal', 'normal', 'normal', 'normal')
_tr7('settings.speed_fast', '速く', '快', 'быстро', 'rápido', 'schnell', 'rapide', 'rápido')
_tr7('settings.audio_reset', '推奨値に戻す', '恢复推荐值', 'Вернуть рекомендуемые', 'Restaurar los recomendados', 'Empfohlene wiederherstellen', 'Rétablir les valeurs recommandées', 'Restaurar os recomendados')
_tr7('settings.audio_reset_btn', '戻す', '恢复', 'Вернуть', 'Restaurar', 'Zurücksetzen', 'Rétablir', 'Restaurar')
_tr7('settings.look_title', '見た目と言語', '外观与语言', 'Вид и язык', 'Aspecto e idioma', 'Aussehen und Sprache', 'Apparence et langue', 'Aparência e idioma')
_tr7('settings.language', '言語', '语言', 'Язык', 'Idioma', 'Sprache', 'Langue', 'Idioma')
_tr7('settings.language_sub', 'サンプルのセリフの言語も変わる。', '示例台词的语言也会一起改变。', 'Меняется и язык образцовых фраз.', 'También cambia el idioma de las frases de ejemplo.', 'Ändert auch die Sprache der Beispielsätze.', 'Change aussi la langue des phrases d’exemple.', 'Muda também o idioma das frases de exemplo.')
_tr7('settings.behaviour_title', 'ふるまい', '行为', 'Поведение', 'Comportamiento', 'Verhalten', 'Comportement', 'Comportamento')
_tr7('settings.guide_title', 'ガイド', '指南', 'Справочник', 'Guía', 'Leitfaden', 'Guide', 'Guia')
_tr7('settings.guide_row', 'なぜ顎、重心、呼吸なのか', '为什么是下巴、重心和呼吸', 'Почему челюсть, центр тяжести и дыхание', 'Por qué mandíbula, centro y respiración', 'Warum Kiefer, Schwerpunkt und Atem', 'Pourquoi mâchoire, ancrage et souffle', 'Por que mandíbula, centro e respiração')
_tr7('settings.tour_row', 'アプリのツアー', '应用导览', 'Экскурсия по приложению', 'Recorrido por la app', 'App-Tour', 'Visite de l’app', 'Visita ao app')
_tr7('settings.tour_row_at', 'アプリのツアー — ステップ {n} / {total}', '应用导览 — 第 {n} 步，共 {total} 步', 'Экскурсия по приложению — шаг {n} из {total}', 'Recorrido por la app: paso {n} de {total}', 'App-Tour — Schritt {n} von {total}', 'Visite de l’app — étape {n} sur {total}', 'Visita ao app — passo {n} de {total}')
_tr7('settings.tour_sub', 'どこに何があるかの短い案内。', '简短介绍东西都在哪儿。', 'Короткая экскурсия по тому, где что находится.', 'Un recorrido breve por dónde está cada cosa.', 'Eine kurze Tour, wo was ist.', 'Une brève visite de l’endroit où se trouve quoi.', 'Uma visita curta a onde está o quê.')
_tr7('settings.tour_btn', 'ツアーを始める', '开始导览', 'Начать экскурсию', 'Empezar el recorrido', 'Tour starten', 'Démarrer la visite', 'Iniciar a visita')
_tr7('settings.tour_resume', '続ける', '继续', 'Продолжить', 'Continuar', 'Fortsetzen', 'Continuer', 'Continuar')
_tr7('dialog.timing_title', 'タイミング', '时机', 'Тайминг', 'Tiempos', 'Timing', 'Rythme', 'Tempo')
_tr7('settings.audio_timing_title', 'タイミング', '时机', 'Тайминг', 'Tiempos', 'Timing', 'Rythme', 'Tempo')
_tr7('settings.speed_normal', 'ふつう', '正常', 'нормально', 'normal', 'normal', 'normal', 'normal')
_tr7('history.title', 'セッション履歴', '记录历史', 'История сессий', 'Historial de sesiones', 'Sitzungsverlauf', 'Historique des séances', 'Histórico de sessões')
_tr7('history.subtitle', '心拍つきのセッション（1分以上）はすべてここに保存される。指標は素の心拍から — HRV ではない。', '每一次带心率的记录（至少一分钟）都会保存在这里。指标来自纯心率 — 不是 HRV。', 'Каждая сессия с пульсом (не короче минуты) сохраняется здесь. Показатели — из чистого пульса, не из HRV.', 'Cada sesión con pulso (de al menos un minuto) se guarda aquí. Las métricas salen del pulso puro, no de la HRV.', 'Jede Sitzung mit Puls (mindestens eine Minute) wird hier gespeichert. Die Kennzahlen stammen aus dem reinen Puls — nicht aus HRV.', 'Chaque séance avec pouls (au moins une minute) est enregistrée ici. Les mesures viennent du pouls brut — pas de la VFC.', 'Cada sessão com pulso (pelo menos um minuto) é salva aqui. As métricas vêm do pulso puro — não de HRV.')
_tr7('history.insights_title', 'アプリが気づいたこと', '应用注意到的事', 'Что заметило приложение', 'Lo que la app ha notado', 'Was der App aufgefallen ist', 'Ce que l’app a remarqué', 'O que o app notou')
_tr7('history.analysis_running', '履歴を分析中…', '正在分析历史…', 'Анализирую историю…', 'Analizando el historial…', 'Verlauf wird analysiert…', 'Analyse de l’historique…', 'Analisando o histórico…')
_tr7('history.analysis_stamp', '{when} の分析', '{when} 的分析', 'Анализ от {when}', 'Análisis de {when}', 'Analyse vom {when}', 'Analyse du {when}', 'Análise de {when}')
_tr7('history.recompute', '再計算', '重新计算', 'Пересчитать', 'Recalcular', 'Neu berechnen', 'Recalculer', 'Recalcular')
_tr7('history.trend_title', 'セッションをまたいだ推移', '跨记录的趋势', 'Динамика по сессиям', 'Evolución entre sesiones', 'Verlauf über die Sitzungen', 'Évolution entre séances', 'Evolução entre sessões')
_tr7('history.trend_baseline', 'セッションごとの安静時ベースライン（BPM） — 古いものが左', '每次记录的静息基线（BPM）— 越旧越靠左', 'Базовая линия покоя (уд/мин) по сессиям — старые слева', 'Línea base en reposo (ppm) por sesión: las más antiguas a la izquierda', 'Ruhebasislinie (S/min) pro Sitzung — die ältesten links', 'Ligne de base au repos (bpm) par séance — les plus anciennes à gauche', 'Linha de base em repouso (bpm) por sessão — as mais antigas à esquerda')
_tr7('history.trend_avg', 'セッションごとの平均心拍（BPM） — 古いものが左', '每次记录的平均心率（BPM）— 越旧越靠左', 'Средний пульс (уд/мин) по сессиям — старые слева', 'Pulso medio (ppm) por sesión: las más antiguas a la izquierda', 'Durchschnittspuls (S/min) pro Sitzung — die ältesten links', 'Pouls moyen (bpm) par séance — les plus anciennes à gauche', 'Pulso médio (bpm) por sessão — as mais antigas à esquerda')
_tr7('history.trend_delta', '{first} → {last} BPM、推移 {slope:+.1f} BPM/週', '{first} → {last} BPM，趋势 {slope:+.1f} BPM/周', '{first} → {last} уд/мин, тренд {slope:+.1f} уд/мин в неделю', '{first} → {last} ppm, tendencia {slope:+.1f} ppm/semana', '{first} → {last} S/min, Trend {slope:+.1f} S/min pro Woche', '{first} → {last} bpm, tendance {slope:+.1f} bpm/semaine', '{first} → {last} bpm, tendência {slope:+.1f} bpm/semana')
_tr7('history.trend_need_more', 'セッションがまだ近すぎて推移が出せない — 数日たってからまた見て。', '记录之间还太密集，看不出趋势 — 过几天再来看。', 'Сессии пока слишком близко друг к другу для тренда — загляни через несколько дней.', 'Las sesiones están aún demasiado juntas para una tendencia: vuelve dentro de unos días.', 'Die Sitzungen liegen für einen Trend noch zu dicht beieinander — schau in ein paar Tagen wieder rein.', 'Les séances sont encore trop rapprochées pour une tendance — reviens dans quelques jours.', 'As sessões ainda estão muito próximas para uma tendência — volte daqui a alguns dias.')
_tr7('history.empty_period', 'この期間にはまだ何もない。', '这个时间段还没有内容。', 'В этом периоде пока ничего.', 'Todavía no hay nada en este periodo.', 'In diesem Zeitraum noch nichts.', 'Rien dans cette période pour l’instant.', 'Ainda nada neste período.')
_tr7('history.period.hour', '時間', '小时', 'Час', 'Hora', 'Stunde', 'Heure', 'Hora')
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
_tr7('history.col_over', 'しきい値超え', '超阈', 'Выше порога', 'Sobre el límite', 'Über der Grenze', 'Au-delà du seuil', 'Acima do limite')
_tr7('history.col_peak', '負荷のピーク', '负荷峰值', 'Пик нагрузки', 'Pico de carga', 'Last-Spitze', 'Pic de charge', 'Pico de carga')
_tr7('history.info_more', 'ⓘ どういう意味', 'ⓘ 这是什么意思', 'ⓘ что это значит', 'ⓘ qué significa', 'ⓘ was das bedeutet', 'ⓘ ce que ça veut dire', 'ⓘ o que significa')
_tr7('history.info_less', 'ⓘ 隠す', 'ⓘ 隐藏', 'ⓘ скрыть', 'ⓘ ocultar', 'ⓘ ausblenden', 'ⓘ masquer', 'ⓘ esconder')
_tr7('history.export_extra', 'あわせて保存されました：\n{files}', '同时还保存了：\n{files}', 'Вместе с этим сохранено:\n{files}', 'También se guardó lo siguiente:\n{files}', 'Zusätzlich gespeichert:\n{files}', 'Enregistré également :\n{files}', 'Junto com ele, também foram salvos:\n{files}')
_tr7('history.export_col.longest_above_s', 'しきい値超えの最長 (秒)', '超过阈值最长 (秒)', 'дольше всего выше порога (с)', 'más largo sobre el umbral (s)', 'längste Zeit über Schwelle (s)', 'plus long au-dessus du seuil (s)', 'mais longo acima do limiar (s)')
_tr7('history.export_col.above_runs', 'しきい値超えの回数', '超阈值次数', 'участков выше порога', 'tramos sobre el umbral', 'Abschnitte über Schwelle', 'segments au-dessus du seuil', 'trechos acima do limiar')
_tr7('history.export_col.cancelled_dip', '低下で中断', '因回落中断', 'отменено спадом', 'cancelado por caída', 'durch Abfall abgebrochen', 'annulé par une baisse', 'cancelado por queda')
_tr7('history.export_col.cancelled_gap', '欠測で中断', '因断连中断', 'отменено пропаданием', 'cancelado por corte', 'durch Ausfall abgebrochen', 'annulé par une coupure', 'cancelado por falha')
_tr7('history.export_col.hold_s', '必要な継続 (秒)', '所需持续 (秒)', 'нужное удержание (с)', 'retención necesaria (s)', 'nötiges Halten (s)', 'maintien requis (s)', 'retenção necessária (s)')
_tr7('history.export_col.context', '文脈', '情境', 'контекст', 'contexto', 'Kontext', 'contexte', 'contexto')
_tr7('history.effect_few', '今は {n} 件 — 判断には足りません', '目前 {n} 次 — 还不足以下结论', 'пока {n} — мало для выводов', 'por ahora {n}: pocos para afirmar nada', 'bisher {n} — zu wenig für eine Aussage', 'pour l’instant {n} — trop peu pour conclure', 'por agora {n} — poucos para afirmar')
_tr7('history.effect_empty', '測定できる合図がまだ一度も鳴っていません。', '还没有任何可供测量的提醒响起。', 'Пока не прозвучала ни одна подсказка, которую можно измерить.', 'Todavía no ha sonado ningún aviso que se pueda medir.', 'Es ist noch kein Hinweis erklungen, den man messen könnte.', 'Aucun rappel mesurable n’a encore retenti.', 'Ainda não soou nenhum aviso que se possa medir.')
_tr7('cue.category.grounding', '重心', '重心', 'опора', 'centro', 'Schwerpunkt', 'ancrage', 'centro')
_tr7('cue.category.jaw', '顎', '下颌', 'челюсть', 'mandíbula', 'Kiefer', 'mâchoire', 'mandíbula')
_tr7('cue.category.release', '脱力', '松开', 'расслабление', 'soltar', 'Lösen', 'relâchement', 'soltar')
_tr7('cue.category.breath', '呼吸', '呼吸', 'дыхание', 'respiración', 'Atem', 'souffle', 'respiração')
_tr7('history.rhythm_title', '続けぐあい', '规律性', 'Регулярность', 'Constancia', 'Regelmäßigkeit', 'Régularité', 'Regularidade')
_tr7('history.days_played', 'セッションのあった日 · 年', '有记录的天数 · 年', 'Дней с сессией · год', 'Días con sesión · año', 'Tage mit Sitzung · Jahr', 'Jours avec séance · an', 'Dias com sessão · ano')
_tr7('history.grid_less', '少ない', '较少', 'меньше', 'menos', 'weniger', 'moins', 'menos')
_tr7('history.grid_more', '多い', '较多', 'больше', 'más', 'mehr', 'plus', 'mais')
_tr7('history.detail_title', 'セッションを間近で', '近看一次记录', 'Одна сессия вблизи', 'Una sesión de cerca', 'Eine Sitzung aus der Nähe', 'Une séance de près', 'Uma sessão de perto')
_tr7('history.detail_peak', '最高心拍', '最高心率', 'Самый высокий пульс', 'Pulso más alto', 'Höchster Puls', 'Pouls le plus haut', 'Pulso mais alto')
_tr7('history.detail_hrr', '回復', '恢复', 'Восстановление', 'Recuperación', 'Erholung', 'Récupération', 'Recuperação')
_tr7('history.detail_hint', '表の行をクリックすると、別のセッションを見られる。', '点击表格中的某一行即可查看另一次记录。', 'Нажми на строку в таблице, чтобы посмотреть другую сессию.', 'Haz clic en una fila de la tabla para ver otra sesión.', 'Klick auf eine Zeile in der Tabelle, um eine andere Sitzung anzusehen.', 'Clique sur une ligne du tableau pour voir une autre séance.', 'Clique numa linha da tabela para ver outra sessão.')
_tr7('history.detail_empty', 'まだセッションがない — ここにその曲線が出る。', '还没有记录 — 它的曲线会显示在这里。', 'Сессий пока нет — здесь появится её кривая.', 'Aún no hay sesiones: aquí aparecerá su curva.', 'Noch keine Sitzung — hier erscheint ihre Kurve.', 'Pas encore de séance — sa courbe apparaîtra ici.', 'Ainda não há sessão — a sua curva aparece aqui.')
_tr7('history.detail_no_curve', 'このセッションは古いバージョンのもので、曲線はもう復元できない。新しいセッションは保存している。', '这次记录来自旧版本，曲线已无法还原。新的记录会保存曲线。', 'Эта сессия из более старой версии, её кривую уже не восстановить. Новые сессии её сохраняют.', 'Esta sesión viene de una versión anterior, así que su curva ya no se puede reconstruir. Las nuevas sí la guardan.', 'Diese Sitzung stammt aus einer älteren Version, ihre Kurve lässt sich nicht mehr rekonstruieren. Neue Sitzungen speichern sie.', 'Cette séance vient d’une version plus ancienne, sa courbe ne peut plus être reconstituée. Les nouvelles la conservent.', 'Esta sessão vem de uma versão mais antiga, por isso a curva já não pode ser reconstruída. As novas a salvam.')
_tr7('history.export_btn', '表にエクスポート', '导出为表格', 'Экспорт в таблицу', 'Exportar a una hoja de cálculo', 'In eine Tabelle exportieren', 'Exporter vers un tableur', 'Exportar para uma planilha')
_tr7('history.export_filetype', 'Excel 用の表（CSV）', 'Excel 表格（CSV）', 'Таблица для Excel (CSV)', 'Hoja de cálculo de Excel (CSV)', 'Excel-Tabelle (CSV)', 'Tableur Excel (CSV)', 'Planilha do Excel (CSV)')
_tr7('history.export_empty', 'エクスポートするものがまだない — まず心拍センサーつきでセッションをこなして。', '还没有可导出的内容 — 先带着心率传感器玩一次。', 'Пока нечего экспортировать — сначала проведи сессию с датчиком пульса.', 'Todavía no hay nada que exportar: juega antes una sesión con el sensor de pulso.', 'Noch nichts zum Exportieren — spiel zuerst eine Sitzung mit dem Pulssensor.', 'Rien à exporter pour l’instant — joue d’abord une séance avec le capteur de pouls.', 'Ainda não há nada para exportar — jogue primeiro uma sessão com o sensor de pulso.')
_tr7('history.export_done', '{n} セッションを {path} に保存した。', '已把 {n} 次记录保存到 {path}。', 'Сохранено сессий: {n} — в {path}.', 'Se guardaron {n} sesiones en {path}.', '{n} Sitzungen in {path} gespeichert.', '{n} séances enregistrées dans {path}.', 'Foram salvas {n} sessões em {path}.')
_tr7('history.export_failed', 'エクスポートに失敗した：{err}', '导出失败：{err}', 'Экспорт не удался: {err}', 'La exportación falló: {err}', 'Export fehlgeschlagen: {err}', 'L’export a échoué : {err}', 'A exportação falhou: {err}')
_tr7('history.export_col.date', '日付', '日期', 'Дата', 'Fecha', 'Datum', 'Date', 'Data')
_tr7('history.export_col.start', '開始', '开始', 'Начало', 'Inicio', 'Beginn', 'Début', 'Início')
_tr7('history.export_col.duration_min', '長さ（分）', '时长（分钟）', 'Длина (мин)', 'Duración (min)', 'Länge (Min)', 'Durée (min)', 'Duração (min)')
_tr7('history.export_col.avg_bpm', '平均 BPM', '平均 BPM', 'Средний BPM', 'BPM medio', 'Durchschnitts-BPM', 'BPM moyen', 'BPM médio')
_tr7('history.export_col.min_bpm', '最低 BPM', '最低 BPM', 'Минимальный BPM', 'BPM mínimo', 'Niedrigster BPM', 'BPM le plus bas', 'BPM mais baixo')
_tr7('history.export_col.max_bpm', '最高 BPM', '最高 BPM', 'Максимальный BPM', 'BPM máximo', 'Höchster BPM', 'BPM le plus haut', 'BPM mais alto')
_tr7('history.export_col.baseline_bpm', '安静時ベースライン', '静息基线', 'Базовая линия покоя', 'Línea base en reposo', 'Ruhebasislinie', 'Ligne de base au repos', 'Linha de base em repouso')
_tr7('history.export_col.over_min', 'しきい値超え（分）', '超阈（分钟）', 'Выше порога (мин)', 'Sobre el límite (min)', 'Über der Grenze (Min)', 'Au-dessus du seuil (min)', 'Acima do limite (min)')
_tr7('history.export_col.peak_stress', '負荷のピーク', '负荷峰值', 'Пик нагрузки', 'Pico de carga', 'Last-Spitze', 'Pic de charge', 'Pico de carga')
_tr7('history.export_col.hrr_bpm', '回復（HRR）', '恢复（HRR）', 'Восстановление (HRR)', 'Recuperación (HRR)', 'Erholung (HRR)', 'Récupération (HRR)', 'Recuperação (HRR)')
_tr7('history.export_col.calm_min', '平静（分）', '平静（分钟）', 'Покой (мин)', 'Calma (min)', 'Ruhig (Min)', 'Calme (min)', 'Calmo (min)')
_tr7('history.export_col.raised_min', 'やや上昇（分）', '略高（分钟）', 'Повышенная (мин)', 'Elevada (min)', 'Erhöht (Min)', 'Élevée (min)', 'Elevada (min)')
_tr7('history.export_col.high_min', '高い（分）', '偏高（分钟）', 'Высокая (мин)', 'Alta (min)', 'Hoch (Min)', 'Haute (min)', 'Alta (min)')
_tr7('history.export_col.critical_min', 'ピーク（分）', '高峰（分钟）', 'Пик (мин)', 'Pico (min)', 'Spitze (Min)', 'Pic (min)', 'Pico (min)')

# --- jazyk toho, co appka kresli DO HRY --------------------------------
# Samostatny od jazyka okna: HUD vlavo dole a popisky pod vizualmi koncia
# na streame a na screenshotoch v obchode, kde ich citaju aj ludia, ktori
# jazyk rozhrania nevedia.
STRINGS.update({
    'settings.game_lang': _sk_en('Jazyk v hre', 'In-game language'),
    'settings.game_lang_same': _sk_en('Rovnaký ako appka', 'Same as the app'),
    'settings.game_lang_sub': _sk_en(
        'Jazyk textu, ktorý appka kreslí do hry — panel s tepom aj popisky pod '
        'vizuálmi. Toto vidia aj diváci na streame, preto je predvolená '
        'angličtina, aj keď appka beží po slovensky.',
        'The language of the text the app draws into the game — the heart-rate '
        'panel and the captions under the visuals. Your stream viewers see this '
        'too, so English is the default even when the app itself is not.'),
    'log.game_lang': _sk_en('Jazyk v hre: {lang}', 'In-game language: {lang}'),
})
_tr7('settings.game_lang', 'ゲーム中の言語', '游戏中的语言', 'Язык в игре', 'Idioma en el juego', 'Sprache im Spiel', 'Langue en jeu', 'Idioma no jogo')
_tr7('settings.game_lang_same', 'アプリと同じ', '与应用相同', 'Как в приложении', 'El mismo que la app', 'Wie die App', 'Comme l’app', 'O mesmo do app')
_tr7('settings.game_lang_sub', 'アプリがゲーム中に描く文字の言語 — 心拍パネルとビジュアルの下の説明。これはストリームの視聴者にも見えるので、アプリ自体が別の言語でも既定は英語。', '应用绘制到游戏里的文字语言 — 心率面板和视觉效果下方的说明。直播观众也会看到，所以即使应用本身不是英文，默认也用英文。', 'Язык текста, который приложение рисует в игре, — панель пульса и подписи под визуалами. Это видят и зрители на стриме, поэтому по умолчанию английский, даже если само приложение на другом языке.', 'El idioma del texto que la app dibuja dentro del juego: el panel de pulso y los rótulos bajo los visuales. Tus espectadores también lo ven, por eso el inglés es el valor por defecto aunque la app no lo esté.', 'Die Sprache des Textes, den die App ins Spiel zeichnet — das Puls-Panel und die Beschriftungen unter den Visuals. Das sehen auch deine Stream-Zuschauer, deshalb ist Englisch die Vorgabe, selbst wenn die App es nicht ist.', 'La langue du texte que l’app dessine dans le jeu — le panneau de pouls et les légendes sous les visuels. Tes spectateurs le voient aussi, c’est pourquoi l’anglais est la valeur par défaut même si l’app ne l’est pas.', 'O idioma do texto que o app desenha dentro do jogo — o painel de pulso e as legendas embaixo dos visuais. Os seus espectadores também o veem, por isso o inglês é o padrão mesmo quando o app em si não está em inglês.')

# --- stranka Ucinnost --------------------------------------------------
# POZOR: stranka Ucinnost este NEEXISTUJE - je to nova obrazovka z fazy 5.
# Tento jediny retazec tu lezi dopredu zamerne: je to rozhodnuta formulacia
# a rozhodnute formulacie sa medzi sedeniami stracaju lahsie nez kod.
#
# Patri na prazdny stav tej stranky, ktory bude prve tyzdne NORMALNY stav,
# nie chyba. Prazdne stavy, ktore appka uz ma ("Zatiaľ žiadna relácia.
# Zapni senzor tepu..."), su konkretnejsie a nemenia sa - tento je iny
# pripad: relacie uz su, len ich zatial nie je dost na porovnanie. Preto
# neodkazuje na ziadne tlacidlo; jedina odpoved je hrat dalej.
STRINGS.update({
    'efficacy.empty': _sk_en(
        'Zatiaľ nič. Nazbiera sa to hraním, nie čakaním.',
        'Nothing yet. This builds up by playing, not by waiting.'),

    # Riadok do logu po doručenej hláške. ROVNAKÝ v oboch ramenách —
    # v hlasnom aj v tichom. Hráč aj tak počuje, či niečo zaznelo, takže
    # zaslepiť sa to nedá, ale log nemá byť ďalším miestom, kde sa ramená
    # rozchádzajú. Preto tu nie je ani slovo o tom, či sa hovorilo.
    'log.cue_delivered': _sk_en('Somatická pripomienka: {label}',
                                'Somatic cue: {label}'),
    'log.cue_visual_failed': _sk_en(
        'In-game vizuál sa nevykreslil — táto hláška sa do merania nezaráta.',
        'The in-game visual did not render — this cue is excluded from measurement.'),
})

# --- výpadok tepu: ticho a pravdivo --------------------------------------
# Tep, ktorý appka počula, prestal chodiť (po 12 s ticha alebo keď hodinky
# pustia spojenie). Nie je to „ešte nič neprišlo" — preto vlastná veta pod
# nadpisom „Čakám na tep" a vlastný štítok na Dnes. Žiadny zvuk, okno ani
# nový text v hre: HUD ukáže „--" ako doteraz.
# Reťaz, ktorou tep ide, je hodinky → telefón (Bluetooth) → Wi‑Fi → počítač;
# rady pri výpadku (`insight.cue_dropouts`, `session.end.none_dropouts`)
# hovoria tú istú.
STRINGS.update({
    'dnes.hr_lost': _sk_en('tep vypadol', 'heart rate lost'),
    'kamae.lost_sub': _sk_en(
        'Tep prestal chodiť (hodinky, telefón alebo Wi‑Fi). Kým sa nevráti, nič nemeriam a sama sa neozvem.',
        'Your heart rate stopped coming in (watch, phone or Wi‑Fi). Until it is back, I measure nothing and will not speak up on my own.'),
    'log.hr_back': _sk_en('Tep je späť po {s} s bez signálu.',
                          'Heart rate is back after {s} s without signal.'),
})

# --- koniec relácie: kontext, nie hodnotenie ----------------------------
# Nepýta sa, ako sa hráč cítil. Pýta sa, ČO SA DIALO — aby sa dali
# odfiltrovať večery, keď dve hodiny rozprával. Rozprávanie je najhorší
# konfunder v tomto meraní: mení sa dych a tep ide hore, takže hláška
# vyzerá neúčinne, hoci s tým nemá nič spoločné.
#
# „Preskočiť" musí byť rovnako veľké tlačidlo ako „Uložiť". Keby bolo
# menšie, raz sa odklikne naslepo — a to sú horšie dáta, než keby človek
# nevyplnil nič.
STRINGS.update({
    'session.end.title': _sk_en('Hral si {time}.', 'You played for {time}.'),
    'session.end.cues': _sk_en(
        'Ozvala som sa {n}×. {silent}× som naschvál mlčala, aby som to mala s čím porovnať.',
        'I spoke {n} times. {silent} of those I stayed silent on purpose, so I have something to compare against.'),
    # Preco sa neozvala. Bez toho je 'neozvala som sa' konstatovanie, z
    # ktoreho hrac nevie, ci je appka pokazena, ci bol pokojny, alebo ci
    # mu vypadavali hodinky. Tri velmi rozne veci s velmi roznym riesenim.
    # Len fakt o hranici, nie verdikt o tele: záťaž pod hranicou neznamená,
    # že bolo telo „v pohode" — appka to nevie a nemá to tvrdiť.
    'session.end.none_never': _sk_en(
        'Záťaž sa ani raz nedostala nad hranicu — nemala som prečo sa ozvať.',
        'Your load never crossed the threshold — I had no reason to speak up.'),
    'session.end.none_short': _sk_en(
        'Záťaž hore bola, ale najdlhšie {najdlhsie} s v kuse — potrebujem {treba} s.',
        'Your load did rise, but the longest stretch was {najdlhsie} s — I need {treba} s.'),
    # {n} = koľkokrát výpadok tepu prerušil rozbehnuté počítanie (nie počet
    # všetkých výpadkov). Rada je tá istá ako v `insight.cue_dropouts`:
    # tep ide z hodiniek cez telefón, nie z hodiniek rovno do počítača.
    'session.end.none_dropouts': _sk_en(
        'Tep {n}× vypadol práve počas počítania a počítanie sa zakaždým začalo odznova. Tep ide z hodiniek do telefónu cez Bluetooth a z telefónu cez Wi‑Fi do počítača — maj hodinky pri telefóne a telefón blízko Wi‑Fi routra.',
        'Your heart rate dropped out {n}× while I was counting, and each time the count started over. It goes from the watch to the phone over Bluetooth, and from the phone to the PC over Wi‑Fi — keep the watch near the phone and the phone near the Wi‑Fi router.'),
    # BRÁNA HLÁŠKY (0.2). Za reláciu (aspoň 5 min) ani jedna pauza vo vstupe:
    # hláška nemala kedy prísť (veta nehovorí „hlas“ - v práci ide bez neho).
    # Presne toto sa ukázalo na skutočnom ovládači so zapnutým gyrom - nie je
    # to vina hráča a veta ho z ničoho neobviňuje.
    'session.end.none_nopause': _sk_en(
        'Celý čas som nezachytila ani jednu pauzu vo vstupe — ani pár sekúnd bez klávesnice, myši či ovládača. A práve na ňu čakám, než sa ozvem. Niečo možno hlási vstup bez prestávky, napríklad pohybový senzor ovládača (gyro) alebo páčka bez mŕtvej zóny. Ak hráš s ovládačom, skús v ňom vypnúť gyro.',
        "The whole time I did not catch a single pause in your input — not even a few seconds without keyboard, mouse or controller. And that is exactly what I wait for before I speak up. Something may be reporting input nonstop, such as a controller's motion sensor (gyro) or a stick without a deadzone. If you play with a controller, try turning its gyro off."),
    # Appka sa natiahla, ale brána ju nepustila (záťaž ešte stúpala alebo
    # tep bol v kritickom pásme). Rozhodla ona, nie hráč.
    'session.end.none_withheld': _sk_en(
        'Záťaž bola hore dosť dlho, ale vhodná chvíľa neprišla — buď ešte stúpala, alebo bol tep v pásme Špička. Radšej som mlčala.',
        'Your load was up long enough, but the right moment never came — it was still climbing, or your pulse was in the peak zone. I chose to stay quiet.'),
    'session.end.cues_none': _sk_en('Dnes som sa neozvala ani raz.',
                                    'I did not speak at all today.'),
    # Co mal hrac v sebe - najvacsi vysvetlitelny zdroj rozptylu v meraní.
    'session.context.body_question': _sk_en('Mal si v sebe niečo z tohto?',
                                            'Did you have any of these in you?'),
    'session.context.save_failed': _sk_en(
        'Kontext sa k tejto relácii nepodarilo uložiť — tvoja odpoveď sa neuchovala.',
        'Could not save the context for this session — your answer was not stored.'),
    'session.context.caffeine': _sk_en('kofeín / energeťák', 'caffeine / energy drink'),
    'session.context.alcohol': _sk_en('alkohol', 'alcohol'),
    'session.context.nicotine': _sk_en('nikotín', 'nicotine'),
    'session.context.tired': _sk_en('málo spánku', 'short on sleep'),
    'session.context.question': _sk_en('Dialo sa niečo z tohto?',
                                       'Did any of this happen?'),
    'session.context.why': _sk_en(
        'Keď rozprávaš, mení sa ti dych a tep ide hore. Bez tohto by taký večer vyzeral, že hlášky nefungujú — hoci s tým nemajú nič spoločné.',
        'When you talk, your breathing changes and your heart rate goes up. Without this, such an evening would look like the cues do nothing — when they have nothing to do with it.'),
    'session.context.call': _sk_en('volal som s niekým', 'I was on a call'),
    'session.context.laugh': _sk_en('smial som sa', 'I was laughing'),
    'session.context.grind': _sk_en('grind', 'grinding'),
    'session.context.competitive': _sk_en('súťažné', 'competitive'),
    'session.context.chill': _sk_en('chill', 'chill'),
    'session.end.skip': _sk_en('Preskočiť', 'Skip'),

    # --- dáta: mazanie, export, import ---------------------------------
    'data.title': _sk_en('Tvoje dáta', 'Your data'),
    'data.hint': _sk_en(
        'Tvoj tep, relácie a postrehy ostávajú na tomto počítači. Nastavenia '
        'tiež, okrem textu hlášok: keď hovoria prirodzeným hlasom (Edge, '
        'predvolený), appka pošle ich text službe Microsoft na prevod do reči. '
        'Hlas z Windows nepošle nič.',
        'Your heart rate, sessions and insights stay on this computer. So do '
        'your settings, except the wording of your cues: when they speak in the '
        'natural voice (Edge, the default), the app sends their text to Microsoft '
        'to turn it into speech. The Windows voice sends nothing.'),
    'data.delete.btn': _sk_en('Zmazať históriu', 'Delete history'),
    'data.delete.title': _sk_en('Zmazať históriu?', 'Delete history?'),
    'data.delete.intro': _sk_en('Zmaže sa toto a späť sa to vrátiť nedá:',
                                'This will be deleted and cannot be undone:'),
    'data.delete.sessions': _sk_en('história relácií', 'session history'),
    'data.delete.events': _sk_en('záznamy hlášok', 'cue records'),
    'data.delete.windows': _sk_en('meracie okná', 'measurement windows'),
    'data.delete.insights': _sk_en('postrehy z analýzy', 'computed insights'),
    'data.delete.tts': _sk_en('vyslovené hlášky (cache)', 'spoken cues (cache)'),
    'data.delete.backup': _sk_en('záloha', 'backup'),
    'data.delete.logs': _sk_en('logy', 'logs'),
    'data.delete.empty': _sk_en('(prázdne)', '(empty)'),
    # Kopie historie v starych priecinkoch po migracii (paths.legacy_data_dirs)
    # - jeden riadok na priecinok, len meno priecinka (cesta nesie meno uctu).
    'data.delete.legacy': _sk_en('kópie zo staršej verzie appky (priečinok „{folder}“)',
                                 'copies left by an older version of the app (folder “{folder}”)'),
    'data.delete.confirm': _sk_en('Zmazať', 'Delete'),
    'data.delete.done': _sk_en('Zmazané ({n} položiek).', 'Deleted ({n} items).'),
    # 0.2: balik nesie relacie, meracie okna a postrehy - nie nastavenia,
    # profily, nahravky ani zaznamy hlasok. "Vsetko" slubovalo prenos na
    # iny PC, pri ktorom by sa zvysok stratil.
    'data.export.btn': _sk_en('Exportovať históriu (JSON)', 'Export history (JSON)'),
    'data.export.hint': _sk_en(
        'Celá história aj meracie okná v jednom súbore — na prenos na iný počítač.',
        'The whole history and the measurement windows in one file — to move to another computer.'),
    'data.export.done': _sk_en('Uložené: {path}', 'Saved: {path}'),
    'data.import.btn': _sk_en('Importovať zo súboru', 'Import from a file'),
    'data.import.title': _sk_en('Importovať dáta', 'Import data'),
    'data.import.found': _sk_en('V súbore je {sessions} relácií a {windows} meracích okien.',
                                'The file has {sessions} sessions and {windows} measurement windows.'),
    'data.import.dropped': _sk_en('{n} záznamov sa nedalo prečítať a preskočili sa.',
                                  '{n} records could not be read and were skipped.'),
    # Presne podla kodu: `imported` preskakuju hr_stats.ciste_relacie
    # (zakladna, hranica vysokeho tepu, prah), rebrik, hr_insights, measure
    # (graf ucinku) a hr_stats.posledna_relacia (karta poslednej relacie).
    'data.import.flagged': _sk_en(
        'Importované záznamy sa označia ako cudzie. V Histórii ich uvidíš, ale '
        'appka sa z nich neučí: nevstúpia do tvojej pokojovej základne, hranice '
        'vysokého tepu ani prahu, od ktorého sa ozývam, do postrehov, grafu o '
        'hláškach, karty poslednej relácie, ani do toho, či sa ozývam hlasom, '
        'obrazom, alebo si dám pauzu. Platí to aj pre tvoj vlastný export z '
        'iného počítača.',
        'Imported records are marked as not yours. You will see them in '
        'History, but the app does not learn from them: they stay out of your '
        'resting baseline, your high heart-rate limit and the threshold I speak '
        'up at, the insights, the cue chart, the last-session card, and whether '
        'I speak up with voice, a picture or take a pause. That goes for your '
        'own export from another computer too.'),
    'data.import.question': _sk_en('Zlúčiť ich s tvojimi, alebo nimi tvoje nahradiť?',
                                   'Merge them with yours, or replace yours with them?'),
    'data.import.merge': _sk_en('Zlúčiť s mojimi', 'Merge with mine'),
    'data.import.replace': _sk_en('Nahradiť moje', 'Replace mine'),
    # NAHRADIT je nevratne voci aktualnym suborom - az na druhy klik a so
    # zalohou (data_io.zaloha_pred_importom).
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

    # --- vývojárska vrstva (§3.2) --------------------------------------
    # Čísla zo zadania §2 sú odhady z literatúry, nie z tela tohto hráča.
    # Bez možnosti otočiť ich za behu by sa muselo rebuildovať každý večer.
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
    'dev.param.away_s': _sk_en('Odišiel od PC', 'Away from the PC'),
    'dev.param.min_gap_s': _sk_en('Odstup medzi hláškami', 'Gap between cues'),
    'dev.silent': _sk_en('Podiel tichých hlášok (0–1)', 'Share of silent cues (0–1)'),
    'dev.reset': _sk_en('Východiskové', 'Defaults'),
    'dev.fire': _sk_en('Vystreliť teraz', 'Fire now'),
    'dev.windows': _sk_en('Posledné meracie okná', 'Last measurement windows'),
    'dev.windows_empty': _sk_en('Zatiaľ žiadne.', 'None yet.'),
    'dev.bad_number': _sk_en('Niektoré pole nie je číslo.', 'One of the fields is not a number.'),
    'dev.applied': _sk_en('Ladenie: hodnoty uložené, platia od ďalšej relácie.',
                          'Tuning: values saved, they apply from the next session.'),
})
_tr7('dev.title', 'チューニング', '调参', 'Настройка', 'Ajustes finos', 'Feinabstimmung', 'Réglage', 'Ajuste fino')
_tr7('dev.hint', '文献から来た数字で、あなたの体から来たものではない。変更できるのはセッションの合間だけ — 途中で変えると動く的を測ることになる。各測定ウィンドウはどの値で作られたか覚えている。', '这些数字来自文献，不是来自你的身体。只能在两次记录之间修改 — 中途修改就是在测一个移动的目标。每个测量窗口都记得自己是用哪些值生成的。', 'Числа из литературы, а не из твоего тела. Меняются только между сессиями — посреди сессии ты мерил бы движущуюся мишень. Каждое измерительное окно помнит, с какими значениями возникло.', 'Números de la literatura, no de tu cuerpo. Solo se cambian entre sesiones: a mitad estarías midiendo un blanco en movimiento. Cada ventana de medición recuerda con qué valores se hizo.', 'Zahlen aus der Literatur, nicht aus deinem Körper. Änderbar nur zwischen Sitzungen — mittendrin würdest du ein bewegtes Ziel messen. Jedes Messfenster merkt sich, mit welchen Werten es entstand.', 'Des chiffres tirés de la littérature, pas de ton corps. Modifiables seulement entre les séances — en cours, tu mesurerais une cible mouvante. Chaque fenêtre de mesure retient avec quelles valeurs elle a été faite.', 'Números da literatura, não do seu corpo. Só mudam entre sessões — no meio de uma, você estaria medindo um alvo em movimento. Cada janela de medição lembra com que valores foi feita.')
_tr7('dev.locked', 'セッション中なので変更できない。心拍センサーを切ってから開き直して。', '记录进行中，无法修改。请关闭心率传感器后重新打开。', 'Сессия идёт, менять нельзя. Выключи датчик пульса и открой заново.', 'Hay una sesión en curso, no se pueden cambiar. Apaga el sensor y vuelve a abrir esto.', 'Eine Sitzung läuft, daher gesperrt. Schalte den Sensor aus und öffne das erneut.', 'Une séance est en cours, c’est verrouillé. Coupe le capteur et rouvre ceci.', 'Há uma sessão em andamento, por isso está bloqueado. Desative o sensor e abra isto de novo.')
_tr7('dev.param.stress_threshold', '負荷のしきい値', '负荷阈值', 'Порог нагрузки', 'Umbral de carga', 'Last-Schwelle', 'Seuil de charge', 'Limiar de carga')
_tr7('dev.param.stress_hold_s', 'しきい値を超えている時間', '超过阈值的持续时间', 'Время над порогом', 'Tiempo por encima', 'Zeit über der Schwelle', 'Temps au-dessus du seuil', 'Tempo acima do limiar')
_tr7('dev.param.dip_grace_s', '許容する落ち込み', '容许的回落', 'Допустимый провал', 'Caída tolerada', 'Tolerierter Einbruch', 'Creux toléré', 'Queda tolerada')
_tr7('dev.param.pause_s', '休みのしきい値', '停顿阈值', 'Порог паузы', 'Umbral de pausa', 'Pausen-Schwelle', 'Seuil de pause', 'Limiar de pausa')
_tr7('dev.param.max_wait_s', '最長の待ち時間', '最长等待', 'Максимум ожидания', 'Espera máxima', 'Längste Wartezeit', 'Attente maximale', 'Espera máxima')
_tr7('dev.param.away_s', '席を外した', '离开电脑', 'Отошёл от ПК', 'Se alejó del PC', 'Vom PC weg', 'Absent du PC', 'Longe do PC')
_tr7('dev.param.min_gap_s', 'ひとことの間隔', '提醒间隔', 'Промежуток между подсказками', 'Intervalo entre avisos', 'Abstand zwischen Hinweisen', 'Intervalle entre rappels', 'Intervalo entre lembretes')
_tr7('dev.silent', '黙る割合（0〜1）', '静默比例（0–1）', 'Доля тихих подсказок (0–1)', 'Proporción de avisos silenciosos (0–1)', 'Anteil stiller Hinweise (0–1)', 'Part de rappels silencieux (0–1)', 'Proporção de lembretes silenciosos (0–1)')
_tr7('dev.reset', '既定値', '默认值', 'По умолчанию', 'Por defecto', 'Standardwerte', 'Valeurs par défaut', 'Padrões')
_tr7('dev.fire', '今すぐ出す', '立即触发', 'Выстрелить сейчас', 'Lanzar ahora', 'Jetzt auslösen', 'Déclencher maintenant', 'Disparar agora')
_tr7('dev.windows', '直近の測定ウィンドウ', '最近的测量窗口', 'Последние измерительные окна', 'Últimas ventanas de medición', 'Letzte Messfenster', 'Dernières fenêtres de mesure', 'Últimas janelas de medição')
_tr7('dev.windows_empty', 'まだない。', '还没有。', 'Пока нет.', 'Todavía ninguna.', 'Noch keine.', 'Aucune pour l’instant.', 'Ainda nenhuma.')
_tr7('dev.bad_number', 'どれかの欄が数字ではない。', '有一个字段不是数字。', 'Одно из полей не число.', 'Uno de los campos no es un número.', 'Eines der Felder ist keine Zahl.', 'L’un des champs n’est pas un nombre.', 'Um dos campos não é um número.')
_tr7('dev.applied', 'チューニング：保存した。次のセッションから有効。', '调参：已保存，从下次记录开始生效。', 'Настройка: значения сохранены, действуют со следующей сессии.', 'Ajustes: guardados, se aplican desde la próxima sesión.', 'Feinabstimmung: gespeichert, gilt ab der nächsten Sitzung.', 'Réglage : enregistré, effectif dès la prochaine séance.', 'Ajuste fino: salvo, vale a partir da próxima sessão.')
_tr7('session.end.title', '{time} プレイした。', '你玩了 {time}。', 'Ты играл {time}.', 'Jugaste {time}.', 'Du hast {time} gespielt.', 'Tu as joué {time}.', 'Você jogou por {time}.')
_tr7('session.end.cues', '{n} 回声をかけた。そのうち {silent} 回はわざと黙った — 比べるものが要るから。', '我提醒了 {n} 次。其中 {silent} 次我故意没出声，这样才有得比较。', 'Я подала голос {n} раз. Из них {silent} раз намеренно промолчала — чтобы было с чем сравнить.', 'Hablé {n} veces. De esas, {silent} callé a propósito, para tener con qué comparar.', 'Ich habe {n}× gesprochen. Davon war ich {silent}× absichtlich still, damit ich etwas zum Vergleichen habe.', 'J’ai parlé {n} fois. Dont {silent} fois je me suis tue exprès, pour avoir un point de comparaison.', 'Falei {n} vezes. Dessas, {silent} fiquei em silêncio de propósito, para ter com que comparar.')
_tr7('session.end.none_short', '負荷は上がりましたが、連続で最長 {najdlhsie} 秒 — {treba} 秒必要です。', '负荷确实升高了，但最长连续 {najdlhsie} 秒 — 我需要 {treba} 秒。', 'Нагрузка поднималась, но дольше всего {najdlhsie} с подряд — нужно {treba} с.', 'La carga sí subió, pero lo más largo fueron {najdlhsie} s seguidos: necesito {treba} s.', 'Die Belastung stieg, aber am längsten {najdlhsie} s am Stück — ich brauche {treba} s.', 'La charge est montée, mais au plus long {najdlhsie} s d’affilée — il m’en faut {treba}.', 'A carga subiu, mas no máximo {najdlhsie} s seguidos — preciso de {treba} s.')
_tr7('session.end.cues_none', '今日は一度も声をかけなかった。', '今天我一次也没出声。', 'Сегодня я не подала голос ни разу.', 'Hoy no hablé ni una vez.', 'Heute habe ich kein einziges Mal gesprochen.', 'Aujourd’hui je n’ai pas parlé une seule fois.', 'Hoje não falei nem uma vez.')
_tr7('session.context.body_question', '体に入っていたものはありますか？', '你摄入了以下哪些？', 'Было ли что-то из этого в организме?', '¿Habías tomado algo de esto?', 'Hattest du etwas davon intus?', 'Avais-tu pris l’un de ces produits ?', 'Você tinha algum destes no corpo?')
_tr7('session.context.caffeine', 'カフェイン / エナジードリンク', '咖啡因 / 能量饮料', 'кофеин / энергетик', 'cafeína / bebida energética', 'Koffein / Energydrink', 'caféine / boisson énergisante', 'cafeína / bebida energética')
_tr7('session.context.alcohol', 'アルコール', '酒精', 'алкоголь', 'alcohol', 'Alkohol', 'alcool', 'álcool')
_tr7('session.context.nicotine', 'ニコチン', '尼古丁', 'никотин', 'nicotina', 'Nikotin', 'nicotine', 'nicotina')
_tr7('session.context.tired', '睡眠不足', '睡眠不足', 'мало сна', 'poco sueño', 'wenig Schlaf', 'peu de sommeil', 'pouco sono')
_tr7('session.context.question', 'こういうことはあった？', '有发生这些情况吗？', 'Что-то из этого было?', '¿Pasó algo de esto?', 'Ist etwas davon passiert?', 'Est-ce que quelque chose de tout ça est arrivé ?', 'Aconteceu alguma destas coisas?')
_tr7('session.context.why', '話すと呼吸が変わって心拍が上がる。これがないと、そういう夜は「声かけが効かない」ように見えてしまう — 実際は関係ないのに。', '说话时呼吸会变、心率会升高。没有这一项，这样的夜晚看起来就像提醒没用 — 其实毫无关系。', 'Когда говоришь, меняется дыхание и пульс растёт. Без этого такой вечер выглядел бы так, будто подсказки не работают — хотя дело вообще не в них.', 'Cuando hablas cambia tu respiración y sube el pulso. Sin esto, esa noche parecería que los avisos no sirven, cuando no tienen nada que ver.', 'Beim Sprechen ändert sich die Atmung und der Puls steigt. Ohne das sähe so ein Abend aus, als würden die Hinweise nichts bringen — obwohl es gar nicht an ihnen liegt.', 'Quand tu parles, ta respiration change et ton pouls monte. Sans ça, une telle soirée donnerait l’impression que les rappels ne servent à rien — alors qu’ils n’y sont pour rien.', 'Quando você fala, a respiração muda e o pulso sobe. Sem isto, uma noite dessas pareceria que os lembretes não funcionam — quando não têm nada a ver.')
_tr7('session.context.call', '誰かと通話した', '在语音通话', 'созванивался', 'estuve en una llamada', 'war im Call', 'j’étais en vocal', 'estive numa chamada')
_tr7('session.context.laugh', '笑っていた', '一直在笑', 'смеялся', 'me estuve riendo', 'habe gelacht', 'j’ai ri', 'dei risada')
_tr7('session.context.grind', '作業ゲー', '刷本', 'гринд', 'grindeo', 'Grind', 'grind', 'grind')
_tr7('session.context.competitive', 'ランク・競技', '排位', 'соревновательное', 'competitivo', 'kompetitiv', 'compétitif', 'competitivo')
_tr7('session.context.chill', 'まったり', '休闲', 'чилл', 'relajado', 'entspannt', 'tranquille', 'tranquilo')
_tr7('session.end.skip', 'スキップ', '跳过', 'Пропустить', 'Omitir', 'Überspringen', 'Passer', 'Ignorar')
_tr7('data.title', 'あなたのデータ', '你的数据', 'Твои данные', 'Tus datos', 'Deine Daten', 'Tes données', 'Os seus dados')
_tr7('data.delete.btn', '履歴を削除', '删除历史', 'Удалить историю', 'Borrar historial', 'Verlauf löschen', 'Supprimer l’historique', 'Apagar histórico')
_tr7('data.delete.title', '履歴を削除する？', '删除历史？', 'Удалить историю?', '¿Borrar historial?', 'Verlauf löschen?', 'Supprimer l’historique ?', 'Apagar histórico?')
_tr7('data.delete.intro', 'これが消える。元には戻せない：', '以下内容将被删除，且无法恢复：', 'Будет удалено, и вернуть это нельзя:', 'Se borrará esto y no se puede deshacer:', 'Das wird gelöscht und lässt sich nicht rückgängig machen:', 'Ceci sera supprimé et ne pourra pas être récupéré :', 'Isto será apagado e não pode ser recuperado:')
_tr7('data.delete.sessions', 'セッション履歴', '记录历史', 'история сессий', 'historial de sesiones', 'Sitzungsverlauf', 'historique des séances', 'histórico de sessões')
_tr7('data.delete.windows', '測定ウィンドウ', '测量窗口', 'измерительные окна', 'ventanas de medición', 'Messfenster', 'fenêtres de mesure', 'janelas de medição')
_tr7('data.delete.insights', '分析の所見', '分析结论', 'наблюдения из анализа', 'observaciones del análisis', 'Beobachtungen aus der Analyse', 'observations de l’analyse', 'observações da análise')
_tr7('data.delete.logs', 'ログ', '日志', 'логи', 'registros', 'Logs', 'journaux', 'registros')
_tr7('data.delete.empty', '（空）', '（空）', '(пусто)', '(vacío)', '(leer)', '(vide)', '(vazio)')
_tr7('data.delete.confirm', '削除', '删除', 'Удалить', 'Borrar', 'Löschen', 'Supprimer', 'Apagar')
_tr7('data.delete.done', '削除した（{n} 件）。', '已删除（{n} 项）。', 'Удалено ({n}).', 'Borrado ({n} elementos).', 'Gelöscht ({n} Einträge).', 'Supprimé ({n} éléments).', 'Apagado ({n} itens).')
_tr7('data.export.hint', '履歴と測定ウィンドウをまとめて一つのファイルに — 別のパソコンへ移すため。', '把全部历史和测量窗口放进一个文件 — 便于转移到另一台电脑。', 'Вся история и измерительные окна в одном файле — чтобы перенести на другой компьютер.', 'Todo el historial y las ventanas de medición en un archivo, para pasarlo a otro ordenador.', 'Der ganze Verlauf und die Messfenster in einer Datei — zum Umzug auf einen anderen Rechner.', 'Tout l’historique et les fenêtres de mesure dans un fichier — pour passer sur un autre ordinateur.', 'Todo o histórico e as janelas de medição num arquivo — para levar para outro computador.')
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
_tr7('efficacy.empty', 'まだ何もありません。これは待つのではなく、プレイすることで貯まります。', '还没有数据。这是靠玩累积的，不是靠等。', 'Пока ничего. Это накапливается игрой, а не ожиданием.', 'Todavía nada. Esto se acumula jugando, no esperando.', 'Noch nichts. Das sammelt sich beim Spielen an, nicht beim Warten.', 'Rien pour l’instant. Cela s’accumule en jouant, pas en attendant.', 'Ainda nada. Isto se acumula jogando, não esperando.')
_tr7('log.cue_delivered', '身体へのひとこと：{label}', '身体提醒：{label}', 'Телесное напоминание: {label}', 'Recordatorio corporal: {label}', 'Körper-Hinweis: {label}', 'Rappel corporel : {label}', 'Lembrete corporal: {label}')
_tr7('log.game_lang', 'ゲーム中の言語：{lang}', '游戏中的语言：{lang}', 'Язык в игре: {lang}', 'Idioma en el juego: {lang}', 'Sprache im Spiel: {lang}', 'Langue en jeu : {lang}', 'Idioma no jogo: {lang}')


# --------------------------------------------------------------------------
# Doplnene preklady (final i18n) - realne chybajuce retazce do 7 jazykov.
# Patchuje existujuce zaznamy v STRINGS (nemeni sk/en).
# --------------------------------------------------------------------------
_DOPLNENE_PREKLADY = {
    "kamae.no_hr": {"ja": "心拍を待っています", "zh": "正在等待心率", "ru": "Ожидаю пульс", "es": "Esperando las pulsaciones", "de": "Warte auf den Puls", "fr": "En attente du rythme cardiaque", "pt": "Aguardando o pulso"},
    "settings.hr_status_no_client": {"ja": "待ち受け中ですが、まだ誰もつながっていません", "zh": "正在监听，但还没有设备连接", "ru": "Слушаю, но никто не подключился", "es": "Escuchando, pero no se ha conectado nadie", "de": "Höre zu, aber niemand hat sich verbunden", "fr": "À l'écoute, mais personne ne s'est connecté", "pt": "Ouvindo, mas ninguém se conectou"},
    "settings.hr_status_busy_gave_up": {"ja": "ポートが使用中です — センサーをオフにしました", "zh": "端口被占用 — 传感器已关闭", "ru": "Порт занят — датчик выключен", "es": "El puerto está ocupado — sensor apagado", "de": "Port ist belegt — Sensor ausgeschaltet", "fr": "Le port est occupé — capteur désactivé", "pt": "A porta está ocupada — sensor desligado"},
    "guide.panel_subtitle": {"ja": "それぞれの合図のときに体の中で何が起きているか、そしてアプリが声をかけてきたら何をすればいいか。", "zh": "每条提示出现时你的身体会发生什么，以及当应用出声提醒时你该怎么做。", "ru": "Что происходит в твоём теле при каждой подсказке и что с этим делать, когда приложение подаёт голос.", "es": "Qué pasa en tu cuerpo con cada aviso y qué hacer cuando la app te habla.", "de": "Was in deinem Körper bei jedem Hinweis passiert und was du damit machen kannst, wenn die App sich meldet.", "fr": "Ce qui se passe dans ton corps à chaque signal, et quoi faire quand l'appli te parle.", "pt": "O que acontece no seu corpo a cada aviso e o que fazer quando o app avisa."},
    "about.title": {"ja": "このアプリについて", "zh": "关于", "ru": "О приложении", "es": "Acerca de", "de": "Über die App", "fr": "À propos", "pt": "Sobre"},
    "about.lead": {"ja": "みなさん、こんにちは。Dandurfinです。", "zh": "大家好，我是 Dandurfin。", "ru": "Всем привет, это Dandurfin.", "es": "Hola a todos, aquí Dandurfin.", "de": "Hallo zusammen, hier ist Dandurfin.", "fr": "Salut à tous, ici Dandurfin.", "pt": "Olá, pessoal, aqui é o Dandurfin."},
    "about.body": {"ja": "そもそもZanshinはなぜ生まれたのか。一日の大半をパソコンの前で過ごし、配信をしたりゲームをしたりしている僕は、時間が経つうちにあるパターンに気づきました。ゲームをしていると、僕たちはよく完全な「オートパイロット」状態にすべり込んでしまいます。夢中になりすぎて時間も自分の体のことも見失ってしまうか、逆に、うまくいかないと無駄にティルトして苛立ってしまうか、どちらかなんです。\n\n僕は、激しいアクションの最中でも、ピリピリしたランクマッチの中でも、冷静な頭を保って「フロー」の状態でいられる方法を探していました。そんなときに出会ったのが、残心（ざんしん）という考え方です。武道では、完全に集中しながらもリラックスし、何にでも対応できる澄んだ心の状態を指す言葉です。\n\nこのアプリは、ただの個人的な必要から書きました。燃え尽きないように支えてくれて、ときどき深呼吸をするよう思い出させてくれて、地に足をつけさせてくれる——そんな、そっと背後で働いてくれる相棒がほしかったんです。複雑で難解な修行の話ではありません。ただ、ゲームをもっと楽しんで、もっとうまくプレイして、そして何より、何でもないことでティルトしない。それだけのことです。\n\n僕も同じ世代の多くの人と同じように、ゲームと一緒に育ちました。目の奥では、外から見えるよりずっと多くのことが起きています。Zanshinは、それを平和なやり方で試してみようという僕なりの試みです。気づいてくれて、何も求めず、何も売らないもの。\n\nそして正直に言うと、僕はプログラマーでもアーティストでもありません。このアプリは「バイブコーディング」で書きました——つまりAIと一緒に、一文ずつ、走りながら覚えていったんです。僕が持ち込んだのは、アイデアと、パソコンの前で過ごした長い年月だけです。\n\n僕は巨人の肩の上に立っています。このアプリがやっていることで、僕が考え出したものは何ひとつありません——呼吸も、集中も、ゆるめた顎も、心拍とストレスの研究も、これを書くのに使った道具も。すべて誰かが僕より先に作り、そして誰でも使えるように開いたまま残しておいてくれたものです。だからこそZanshinは、GPLv3ライセンスのもとで無料かつオープンです。誰でもコードを読み、書き換え、次へ渡すことができます——ただ、閉じてしまうことだけはできません。次へ渡す人は、ソースコードと同じライセンスも一緒に手渡さなければなりません。僕はこうして受け継ぎ、こうして同じように渡していきたいのです。\n\nこの考え方にピンとくる人も、ただゲームをして一緒にゆるく過ごしたいだけの人も、ぜひ僕たちのコミュニティに立ち寄ってください：", "zh": "Zanshin 到底是怎么诞生的？作为一个每天有很大一部分时间都泡在电脑前、直播和打游戏的人，我慢慢发现了一个规律。玩游戏时，我们常常会完全进入“自动驾驶”模式。要么是太投入，以至于彻底忘了时间，也忘了自己的身体；要么反过来，一不顺就上头，为不该生气的事情生气。\n\n我一直在找一种方法，让自己即便身处激烈的战斗或紧张的排位赛中，也能保持冷静的头脑，留在“心流”里。也正是在那时，我接触到了 zanshin 这个概念——在武术里，它指的是一种全神贯注、放松、头脑清明、随时准备应对一切的状态。\n\n写这个应用，纯粹是出于我自己一个很简单的需求。我想要一个不起眼、在后台默默帮忙的小助手，让我不至于把自己耗空，时不时提醒我深呼吸一下，把我拉回地面。这里没有什么复杂玄乎的练习，说到底就是为了让我们玩游戏更开心、发挥得更好，最重要的是——别为了鸡毛蒜皮的事上头。\n\n我和同龄的很多人一样，是玩着游戏长大的。眼睛背后发生的事，比别人看到的多得多。Zanshin 是我的一次尝试，想用和平的方式去面对：一个会注意到你、什么都不要、什么都不卖的东西。\n\n再说得直白点：我既不是程序员，也不是美术。这个应用是我用 vibe coding 的方式写出来的——和 AI 一起，一行一行地敲，边做边学。我带进来的，就是这个点子，还有多年泡在电脑前的经历。\n\n我是站在巨人的肩膀上。这个应用所做的一切，没有一样是我发明的——呼吸、专注、放松的下颌、关于心率和压力的研究，还有写它所用的那些工具。这一切都是别人在我之前做好、并且免费公开出来的。正因如此，Zanshin 在 GPLv3 许可证下免费且开放：任何人都可以阅读代码、修改它、把它传下去——唯独不能把它封闭起来。谁把它传下去，就必须连同源代码和同一份许可证一起交出去。我是这样继承来的，也想这样传下去。\n\n如果你认同这样的心态，或者只是想一起打打游戏、聊聊天，一定要来我们的社区坐坐：", "ru": "Почему вообще появился Zanshin? Как человек, который проводит за компьютером огромную часть дня — стримлю и играю, — я со временем заметил закономерность. Играя, мы часто скатываемся в полный «автопилот». Либо увлекаемся так, что теряем счёт времени и забываем о собственном теле, либо, наоборот, ловим ненужный тильт и злимся, когда что-то не выходит.\n\nЯ искал способ сохранять холодную голову и оставаться в «потоке» даже посреди жаркого экшена или в потных ранкед-матчах. Тогда я и наткнулся на понятие zanshin — в боевых искусствах оно означает состояние полной сосредоточенности, расслабленности и ясной головы, готовой ко всему.\n\nЭто приложение я написал из простой личной потребности. Мне хотелось незаметного помощника на фоне, который не даст мне выгореть, время от времени напомнит глубоко вдохнуть и удержит меня на земле. Речь не о каких-то сложных эзотерических упражнениях — просто о том, чтобы игры приносили больше удовольствия, чтобы играть лучше и, главное, чтобы не злиться из-за ерунды.\n\nЯ вырос с играми, как многие из моего поколения. За глазами происходит больше, чем кто-либо видит. Zanshin — моя попытка попробовать по-мирному: что-то, что замечает, ничего не требует и ничего не продаёт.\n\nИ честно: я не программист и не художник. Это приложение я написал вайб-кодингом — то есть вместе с ИИ, строчка за строчкой, учась по ходу дела. То, что привнёс я, — это идея и годы, проведённые за компьютером.\n\nЯ стою на плечах гигантов. Ничего из того, что делает это приложение, я не придумал — дыхание, сосредоточенность, расслабленная челюсть, исследования о пульсе и стрессе, да и инструменты, на которых всё это написано. Всё это кто-то сделал до меня и оставил в свободном доступе. Поэтому Zanshin бесплатный и открытый под лицензией GPLv3: любой может посмотреть код, изменить его и передать дальше — только закрыть его нельзя. Кто передаёт его дальше, должен отдать вместе с ним и исходный код, и ту же самую лицензию. Я получил это так и хочу так же передать дальше.\n\nЕсли тебе близок этот настрой или ты просто хочешь поиграть и потусить, обязательно загляни к нам:", "es": "¿Por qué surgió Zanshin en realidad? Como alguien que pasa gran parte del día delante del PC —haciendo streaming y jugando— con el tiempo me di cuenta de un patrón. Al jugar caemos a menudo en el «piloto automático» total. O nos metemos tanto que perdemos la noción del tiempo y de nuestro propio cuerpo, o al revés, pillamos un tilt innecesario y nos frustramos cuando las cosas no salen.\n\nBuscaba una forma de mantener la cabeza fría y quedarme en el «flow» incluso en plena acción o en partidas sweaty de ranked. Fue entonces cuando di con el concepto de zanshin — que en las artes marciales designa un estado de concentración plena, relajación y mente clara, lista para cualquier cosa.\n\nProgramé esta app por una simple necesidad personal. Quería un ayudante discreto en segundo plano que no me deje quemarme, que de vez en cuando me recuerde respirar hondo y que me mantenga con los pies en la tierra. No se trata de ningún ejercicio esotérico complicado; se trata simplemente de disfrutar más de los juegos, jugar mejor y, sobre todo, no cabrearnos por nada.\n\nCrecí con los videojuegos, como mucha gente de mi generación. Detrás de los ojos pasa más de lo que nadie ve. Zanshin es mi intento de probarlo en paz: algo que se da cuenta, no pide nada y no vende nada.\n\nY os lo digo sin rodeos: no soy programador ni artista. Esta app la hice a base de vibe coding — junto con la IA, línea a línea, aprendiendo sobre la marcha. Lo que puse yo es la idea y los años pasados delante del PC.\n\nEstoy a hombros de gigantes. Nada de lo que hace esta app lo inventé yo — la respiración, la concentración, la mandíbula relajada, la investigación sobre el ritmo cardíaco y el estrés, las herramientas con las que está escrita. Todo eso ya lo hizo alguien antes que yo y lo dejó a disposición de todos. Por eso Zanshin es gratuito y abierto bajo la licencia GPLv3: cualquiera puede leer el código, modificarlo y pasarlo adelante — lo único que no puede es cerrarlo. Quien lo pase adelante tiene que entregar también el código fuente y la misma licencia. Yo lo heredé así y quiero entregarlo de la misma manera.\n\nSi esta forma de ver las cosas te encaja, o si solo quieres echar unas partidas y pasar el rato, pásate sin falta por nuestra comunidad:", "de": "Warum ist Zanshin eigentlich entstanden? Als jemand, der einen großen Teil des Tages am PC verbringt — ich streame und zocke — ist mir mit der Zeit ein Muster aufgefallen. Beim Spielen rutschen wir oft in den kompletten „Autopilot“. Entweder vertiefen wir uns so sehr, dass wir das Zeitgefühl und den eigenen Körper völlig verlieren, oder wir fangen uns umgekehrt unnötigen Tilt ein und ärgern uns, wenn es nicht läuft.\n\nIch habe nach einem Weg gesucht, einen kühlen Kopf zu bewahren und selbst mitten in der Action oder in sweaty Ranked-Matches im „Flow“ zu bleiben. Damals bin ich auf den Begriff Zanshin gestoßen — in den Kampfkünsten bezeichnet er einen Zustand voller Konzentration, Entspannung und eines klaren Kopfes, der auf alles vorbereitet ist.\n\nDiese App habe ich aus einem ganz einfachen persönlichen Bedürfnis geschrieben. Ich wollte einen unaufdringlichen Helfer im Hintergrund, der mich nicht ausbrennen lässt, mich ab und zu ans tiefe Durchatmen erinnert und mich auf dem Boden hält. Es geht um keine komplizierten esoterischen Übungen — es geht einfach darum, dass uns die Spiele mehr Spaß machen, dass wir besser spielen und vor allem, dass wir uns nicht wegen Kleinigkeiten aufregen.\n\nIch bin mit Games aufgewachsen, wie viele aus meiner Generation. Hinter den Augen passiert mehr, als irgendwer sieht. Zanshin ist mein Versuch, es im Frieden zu probieren: etwas, das hinschaut, nichts will und nichts verkauft.\n\nUnd ganz ehrlich: Ich bin weder Programmierer noch Grafiker. Diese App habe ich per Vibe Coding geschrieben — also zusammen mit KI, Satz für Satz, und ich habe im Laufen dazugelernt. Was ich beigetragen habe, ist die Idee und die Jahre, die ich am PC verbracht habe.\n\nIch stehe auf den Schultern von Riesen. Nichts von dem, was die App tut, habe ich erfunden — das Atmen, die Konzentration, der gelöste Kiefer, die Forschung zu Puls und Stress und auch die Werkzeuge, in denen das Ganze geschrieben ist. Das alles hat jemand vor mir gemacht und frei zugänglich gelassen. Deshalb ist Zanshin kostenlos und offen unter der GPLv3-Lizenz: Jeder kann sich den Code ansehen, ihn ändern und weitergeben — nur zumachen darf er ihn nicht. Wer ihn weitergibt, muss den Quellcode und dieselbe Lizenz mitliefern. Ich habe es so geerbt und ich will es genauso weitergeben.\n\nWenn dir diese Einstellung zusagt, oder wenn du einfach zocken und quatschen willst, schau unbedingt bei uns vorbei:", "fr": "Pourquoi Zanshin a-t-il vu le jour, au juste ? En tant que personne qui passe une grande partie de sa journée devant le PC — à streamer et à jouer — j'ai fini par remarquer un schéma qui revient. En jouant, on bascule souvent en mode « pilote automatique » total. Soit on est tellement absorbé qu'on perd complètement la notion du temps et de son propre corps, soit, à l'inverse, on attrape un tilt inutile et on s'agace dès que ça ne va pas.\n\nJe cherchais un moyen de garder la tête froide et de rester dans le « flow » même en pleine action ou dans des parties classées bien sweaty. C'est là que je suis tombé sur le concept de zanshin — qui, dans les arts martiaux, désigne un état de concentration totale, de détente et d'esprit clair, prêt à tout.\n\nJ'ai codé cette appli par simple besoin personnel. Je voulais un assistant discret, en arrière-plan, qui m'empêche de m'épuiser, qui me rappelle de respirer profondément de temps en temps et qui me garde les pieds sur terre. Rien à voir avec des exercices ésotériques compliqués — il s'agit simplement de prendre plus de plaisir à jouer, de mieux jouer et, surtout, de ne pas s'énerver pour un rien.\n\nJ'ai grandi avec les jeux vidéo, comme beaucoup de ma génération. Derrière les yeux, il se passe plus de choses que ce que l'on voit. Zanshin, c'est ma tentative d'essayer en paix : quelque chose qui remarque, ne demande rien et ne vend rien.\n\nEt soyons clairs : je ne suis ni programmeur ni graphiste. J'ai codé cette appli en vibe coding — avec l'IA, ligne par ligne, en apprenant au fur et à mesure. Ce que j'y ai apporté, moi, c'est l'idée et les années passées devant le PC.\n\nJe me tiens sur les épaules de géants. Rien de ce que fait cette appli n'a été inventé par moi — la respiration, la concentration, la mâchoire détendue, les recherches sur le rythme cardiaque et le stress, les outils dans lesquels elle est écrite. Quelqu'un a fait tout ça avant moi et l'a laissé en libre accès. C'est pour ça que Zanshin est gratuit et ouvert sous la licence GPLv3 : n'importe qui peut lire le code, le modifier et le transmettre — il ne peut simplement pas le refermer. Celui qui le transmet doit remettre avec lui le code source et cette même licence. J'en ai hérité ainsi, et je veux le transmettre de la même façon.\n\nSi cet état d'esprit te parle, ou si tu veux juste jouer et passer un bon moment, passe faire un tour dans notre communauté :", "pt": "Por que, afinal, o Zanshin surgiu? Como alguém que passa boa parte do dia no PC — fazendo stream e jogando —, com o tempo percebi um padrão. Jogando, muitas vezes entramos no modo “piloto automático” total. Ou ficamos tão absorvidos que perdemos completamente a noção do tempo e do próprio corpo, ou, ao contrário, entramos num tilt desnecessário e ficamos frustrados quando as coisas dão errado.\n\nEu estava procurando um jeito de manter a cabeça fria e ficar no “flow” mesmo no meio da ação intensa ou de partidas sweaty de ranked. Foi aí que dei de cara com o conceito de zanshin — que, nas artes marciais, designa um estado de concentração total, descontração e mente limpa, pronta para tudo.\n\nEscrevi este app por uma simples necessidade pessoal. Eu queria um ajudante discreto em segundo plano que não me deixasse esgotar, que de vez em quando me lembrasse de respirar fundo e que me mantivesse com os pés no chão. Não são exercícios esotéricos complicados — é simplesmente para a gente se divertir mais com os jogos, jogar melhor e, acima de tudo, não entrar em tilt à toa.\n\nCresci com os jogos, como muita gente da minha geração. Por trás dos olhos acontece mais do que se vê. O Zanshin é a minha tentativa de tentar isso em paz: algo que percebe, não quer nada e não vende nada.\n\nE agora sem rodeios: não sou programador nem artista. Fiz este app com vibe coding — ou seja, junto com a IA, linha por linha, aprendendo pelo caminho. O que eu trouxe foi a ideia e os anos passados no PC.\n\nEstou apoiado nos ombros de gigantes. Nada do que este app faz foi inventado por mim — a respiração, a concentração, a mandíbula solta, a pesquisa sobre frequência cardíaca e estresse, e as ferramentas em que ele foi escrito. Alguém fez tudo isso antes de mim e deixou livremente disponível. É por isso que o Zanshin é gratuito e aberto sob a licença GPLv3: qualquer pessoa pode ver o código, alterá-lo e passá-lo adiante — só não pode fechá-lo. Quem o passa adiante tem de entregar junto também o código-fonte e a mesma licença. Eu o herdei assim e assim quero passá-lo adiante.\n\nSe essa atitude tem a ver com você, ou se você só quer jogar um pouco e bater papo, passe com certeza na nossa comunidade:"},
    "about.links": {"ja": "僕はここにいます", "zh": "在这里找到我", "ru": "Найдёшь меня здесь", "es": "Me encuentras aquí", "de": "Hier findest du mich", "fr": "Retrouve-moi ici", "pt": "Me encontre aqui"},
    "about.between_lines": {"ja": "行間を読む人へ：\n\nこのアプリはストレスを測らない。測るのは、すきま——心拍が告げるものと、あなたが実際に感じるものとの間の。数字は表面、あなたは深み。\n\nそのすきまを自分の中で聞けるようになれば、ほかの場所でも聞こえてくる——人が書くことと思っていること、求めることと必要としていることの間に。\n\n何も失われない。ただ姿を変えるだけ——注意もまた。手のひらは開いたままで。", "zh": "给读得懂字里行间的人：\n\n这个应用不测量压力。它测量的是那道缝隙——你的心率所说的，与你真正所感受的之间。数字是表面；你是深处。\n\n当你学会在自己心里听见那道缝隙，你也会开始在别处听见它——在人们所写的与所想的、所求的与所需的之间。\n\n没有什么会失去。只是转化——注意力也是。把手掌摊开。", "ru": "Для того, кто читает между строк:\n\nЭто приложение не измеряет стресс. Оно измеряет зазор — между тем, что говорит твой пульс, и тем, что ты на самом деле чувствуешь. Число — это поверхность; ты — глубина.\n\nИ когда ты научишься слышать этот зазор в себе, ты начнёшь слышать его и в другом — в том, что люди пишут и что думают, чего просят и что им нужно.\n\nНичто не теряется. Оно лишь преображается — и внимание тоже. Держи ладонь открытой.", "es": "Para quien lee entre líneas:\n\nEsta app no mide el estrés. Mide la brecha — entre lo que dice tu pulso y lo que de verdad sientes. El número es la superficie; tú eres la profundidad.\n\nY cuando aprendas a oír esa brecha en ti, empezarás a oírla también en otras partes — en lo que la gente escribe y lo que piensa, en lo que pide y lo que necesita.\n\nNada se pierde. Solo se transforma — también la atención. Mantén la palma abierta.", "de": "Für den, der zwischen den Zeilen liest:\n\nDiese App misst nicht den Stress. Sie misst die Lücke — zwischen dem, was dein Puls sagt, und dem, was du wirklich fühlst. Die Zahl ist die Oberfläche; du bist die Tiefe.\n\nUnd wenn du lernst, diese Lücke in dir zu hören, wirst du sie auch anderswo hören — in dem, was Menschen schreiben und was sie meinen, worum sie bitten und was sie brauchen.\n\nNichts geht verloren. Es wandelt sich nur — auch die Aufmerksamkeit. Halte die Handfläche offen.", "fr": "Pour celui qui lit entre les lignes :\n\nCette appli ne mesure pas le stress. Elle mesure l'écart — entre ce que dit ton pouls et ce que tu ressens vraiment. Le chiffre est la surface ; toi, tu es la profondeur.\n\nEt quand tu apprendras à entendre cet écart en toi, tu commenceras à l'entendre ailleurs aussi — dans ce que les gens écrivent et ce qu'ils pensent, ce qu'ils demandent et ce dont ils ont besoin.\n\nRien ne se perd. Cela se transforme seulement — l'attention aussi. Garde la paume ouverte.", "pt": "Para quem lê nas entrelinhas:\n\nEste app não mede o estresse. Mede a lacuna — entre o que o seu pulso diz e o que você realmente sente. O número é a superfície; você é a profundidade.\n\nE quando você aprender a ouvir essa lacuna em si mesmo, vai começar a ouvi-la também em outros lugares — no que as pessoas escrevem e no que pensam, no que pedem e no que precisam.\n\nNada se perde. Apenas se transforma — a atenção também. Mantenha a palma aberta."},
    "log.cue_visual_failed": {"ja": "ゲーム内のビジュアルが表示されませんでした——この合図は計測から除外されます。", "zh": "游戏内的视觉提示没有渲染出来——这条提示不计入测量。", "ru": "Внутриигровой визуал не отрисовался — эта подсказка не учитывается в измерении.", "es": "El visual dentro del juego no se mostró — este aviso no se cuenta en la medición.", "de": "Das In-Game-Bild wurde nicht angezeigt — dieser Hinweis zählt nicht in die Messung.", "fr": "Le visuel en jeu ne s'est pas affiché — ce signal est exclu de la mesure.", "pt": "O visual no jogo não foi exibido — este aviso fica excluído da medição."},
    "session.context.save_failed": {"ja": "このセッションのコンテキストを保存できませんでした——回答は保存されませんでした。", "zh": "无法保存这次会话的情境——你的回答没有被保存下来。", "ru": "Не удалось сохранить контекст этой сессии — твой ответ не сохранён.", "es": "No se pudo guardar el contexto de esta sesión — tu respuesta no se ha guardado.", "de": "Der Kontext für diese Sitzung konnte nicht gespeichert werden — deine Antwort wurde nicht behalten.", "fr": "Impossible d'enregistrer le contexte de cette session — ta réponse n'a pas été conservée.", "pt": "Não foi possível salvar o contexto desta sessão — a sua resposta não foi salva."},
    "data.delete.events": {"ja": "合図の記録", "zh": "提示记录", "ru": "записи подсказок", "es": "registros de avisos", "de": "Aufgezeichnete Hinweise", "fr": "enregistrements des signaux", "pt": "registros de avisos"},
    "data.delete.tts": {"ja": "読み上げた合図（キャッシュ）", "zh": "语音提示（缓存）", "ru": "озвученные подсказки (кэш)", "es": "avisos hablados (caché)", "de": "Gesprochene Hinweise (Cache)", "fr": "signaux vocaux (cache)", "pt": "avisos falados (cache)"},
    "data.delete.backup": {"ja": "バックアップ", "zh": "备份", "ru": "резервная копия", "es": "copia de seguridad", "de": "Sicherung", "fr": "sauvegarde", "pt": "cópia de segurança"},
    "history.col_minmax": {"ja": "最小 / 最大", "zh": "最小 / 最大", "ru": "Мин / макс", "es": "Min / max", "de": "Min / max", "fr": "Min / max", "pt": "Mín / máx"},
    # --- Kontext relacie: cinnost (hral/pracoval) + vlastna poznamka ---
    "session.context.activity_question": {"sk": "Hral si, alebo pracoval?", "en": "Were you playing or working?", "ja": "遊んでいた？それとも作業していた？", "zh": "你是在玩，还是在工作？", "ru": "Ты играл или работал?", "es": "¿Estabas jugando o trabajando?", "de": "Hast du gespielt oder gearbeitet?", "fr": "Tu jouais ou tu travaillais ?", "pt": "Você estava jogando ou trabalhando?"},
    "session.context.activity.play": {"sk": "Hral som", "en": "Playing", "ja": "ゲーム", "zh": "在玩", "ru": "Играл", "es": "Jugando", "de": "Gespielt", "fr": "Je jouais", "pt": "Jogando"},
    "session.context.activity.work": {"sk": "Pracoval som", "en": "Working", "ja": "作業", "zh": "在工作", "ru": "Работал", "es": "Trabajando", "de": "Gearbeitet", "fr": "Je travaillais", "pt": "Trabalhando"},
    "session.context.note_label": {"sk": "Vlastná poznámka (nepovinné)", "en": "Your own note (optional)", "ja": "自由メモ（任意）", "zh": "自己的备注（可选）", "ru": "Своя заметка (необязательно)", "es": "Nota propia (opcional)", "de": "Eigene Notiz (optional)", "fr": "Note perso (facultatif)", "pt": "Sua nota (opcional)"},
    "hud.quick_label": {"sk": "Tep v hre", "en": "In-game HR", "ja": "ゲーム内の心拍", "zh": "游戏内心率", "ru": "Пульс в игре", "es": "Pulso en juego", "de": "Puls im Spiel", "fr": "FC en jeu", "pt": "Pulso no jogo"},
    "history.export_col.activity": {"sk": "činnosť", "en": "activity", "ja": "活動", "zh": "活动", "ru": "активность", "es": "actividad", "de": "Aktivität", "fr": "activité", "pt": "atividade"},
    "history.export_col.hud_seen": {"sk": "HUD videný %", "en": "HUD seen %", "ja": "HUD表示率", "zh": "HUD可见%", "ru": "HUD виден %", "es": "HUD visto %", "de": "HUD sichtbar %", "fr": "HUD vu %", "pt": "HUD visto %"},
    "history.export_col.note": {"sk": "poznámka", "en": "note", "ja": "メモ", "zh": "备注", "ru": "заметка", "es": "nota", "de": "Notiz", "fr": "note", "pt": "nota"},
    # --- 1. kolo premenných: choroba/šport-pred, spánok, subjektívna vrstva ---
    "session.context.illness": {"sk": "cítim sa chorý / nanič", "en": "feeling ill / off", "ja": "体調が悪い", "zh": "感觉不舒服/生病", "ru": "нездоровится / болею", "es": "me siento mal / enfermo", "de": "fühle mich krank / mies", "fr": "je me sens malade / patraque", "pt": "me sinto doente / mal"},
    "session.context.exercise_before": {"sk": "pred hraním som sa hýbal/zadýchal", "en": "moved/exerted before playing", "ja": "プレイ前に動いた/息が上がった", "zh": "玩之前运动/喘过气", "ru": "перед игрой двигался/запыхался", "es": "me moví/agité antes de jugar", "de": "vor dem Spielen bewegt/außer Atem", "fr": "bougé/essoufflé avant de jouer", "pt": "me mexi / fiquei ofegante antes de jogar"},
    "session.sleep.q": {"sk": "Spánok minulú noc", "en": "Sleep last night", "ja": "昨夜の睡眠", "zh": "昨晚的睡眠", "ru": "Сон прошлой ночью", "es": "Sueño anoche", "de": "Schlaf letzte Nacht", "fr": "Sommeil la nuit dernière", "pt": "Sono na noite passada"},
    "session.sleep.rested": {"sk": "vyspatý", "en": "rested", "ja": "よく寝た", "zh": "睡得好", "ru": "выспался", "es": "descansado", "de": "ausgeschlafen", "fr": "reposé", "pt": "descansado"},
    "session.sleep.mid": {"sk": "stredne", "en": "so-so", "ja": "まあまあ", "zh": "一般", "ru": "средне", "es": "regular", "de": "mittel", "fr": "moyen", "pt": "mais ou menos"},
    "session.sleep.broken": {"sk": "rozbitý", "en": "broken", "ja": "ボロボロ", "zh": "很差", "ru": "разбитый", "es": "fatal", "de": "mies", "fr": "haché", "pt": "péssimo"},
    "session.felt.header": {"sk": "Ako sa to cítilo", "en": "How it felt", "ja": "どう感じた", "zh": "感觉如何", "ru": "Как это ощущалось", "es": "Cómo se sintió", "de": "Wie es sich anfühlte", "fr": "Ressenti", "pt": "Como você se sentiu"},
    "session.felt.load": {"sk": "Vnímaná záťaž", "en": "Perceived load", "ja": "感じた負荷", "zh": "主观强度", "ru": "Ощущаемая нагрузка", "es": "Carga percibida", "de": "Empfundene Last", "fr": "Charge ressentie", "pt": "Carga percebida"},
    "session.felt.load_hint": {"sk": "0 = úplný pokoj, 10 = maximálne vypätie", "en": "0 = totally calm, 10 = maxed out", "ja": "0＝完全に穏やか、10＝極限", "zh": "0＝完全平静，10＝极度紧绷", "ru": "0 = полный покой, 10 = на пределе", "es": "0 = calma total, 10 = al límite", "de": "0 = ganz ruhig, 10 = am Limit", "fr": "0 = tout calme, 10 = à fond", "pt": "0 = calma total, 10 = no limite"},
    "session.felt.valence": {"sk": "Bolo ti skôr dobre, či zle?", "en": "Did it feel good or bad?", "ja": "気分は良かった？悪かった？", "zh": "感觉是好还是坏？", "ru": "Было приятно или неприятно?", "es": "¿Te sentiste bien o mal?", "de": "Eher gut oder schlecht?", "fr": "Plutôt bien ou mal ?", "pt": "Foi mais para bom ou para ruim?"},
    "session.felt.valence.-2": {"sk": "zle", "en": "bad", "ja": "悪い", "zh": "差", "ru": "плохо", "es": "mal", "de": "schlecht", "fr": "mal", "pt": "ruim"},
    "session.felt.valence.-1": {"sk": "skôr zle", "en": "rather bad", "ja": "やや悪い", "zh": "偏差", "ru": "скорее плохо", "es": "algo mal", "de": "eher schlecht", "fr": "plutôt mal", "pt": "mais para ruim"},
    "session.felt.valence.0": {"sk": "neutrál", "en": "neutral", "ja": "ふつう", "zh": "一般", "ru": "нейтрально", "es": "neutral", "de": "neutral", "fr": "neutre", "pt": "neutro"},
    "session.felt.valence.1": {"sk": "skôr dobre", "en": "rather good", "ja": "やや良い", "zh": "偏好", "ru": "скорее хорошо", "es": "algo bien", "de": "eher gut", "fr": "plutôt bien", "pt": "mais para bom"},
    "session.felt.valence.2": {"sk": "dobre", "en": "good", "ja": "良い", "zh": "好", "ru": "хорошо", "es": "bien", "de": "gut", "fr": "bien", "pt": "bom"},
    "session.felt.body_q": {"sk": "Keď to bolo najintenzívnejšie, telo bolo skôr…", "en": "At the most intense moment, your body was…", "ja": "一番きつかったとき、体はどうだった…", "zh": "最紧张的时候，身体更偏…", "ru": "В самый напряжённый момент тело было скорее…", "es": "En el momento más intenso, tu cuerpo estaba…", "de": "Im intensivsten Moment war dein Körper eher…", "fr": "Au moment le plus intense, ton corps était plutôt…", "pt": "No momento mais intenso, o corpo estava mais…"},
    "session.felt.body.ok": {"sk": "nič zvláštne", "en": "nothing special", "ja": "特に何も", "zh": "没什么特别", "ru": "ничего особого", "es": "nada especial", "de": "nichts Besonderes", "fr": "rien de spécial", "pt": "nada de especial"},
    "session.felt.body.flow": {"sk": "sústredený (flow)", "en": "focused (flow)", "ja": "集中(フロー)", "zh": "专注(心流)", "ru": "сосредоточен (поток)", "es": "concentrado (flow)", "de": "fokussiert (Flow)", "fr": "concentré (flow)", "pt": "focado (flow)"},
    "session.felt.body.wired": {"sk": "nabudený", "en": "wired", "ja": "そわそわ", "zh": "亢奋", "ru": "на взводе", "es": "acelerado", "de": "aufgedreht", "fr": "surexcité", "pt": "ligado"},
    "session.felt.body.tense": {"sk": "napätý (čeľusť/plecia)", "en": "tense (jaw/shoulders)", "ja": "緊張(顎/肩)", "zh": "紧绷(下巴/肩)", "ru": "напряжён (челюсть/плечи)", "es": "tenso (mandíbula/hombros)", "de": "verspannt (Kiefer/Schultern)", "fr": "tendu (mâchoire/épaules)", "pt": "tenso (maxilar/ombros)"},
    "session.felt.body.sick": {"sk": "zle od žalúdka", "en": "queasy stomach", "ja": "胃がむかむか", "zh": "反胃", "ru": "мутит в животе", "es": "revuelto el estómago", "de": "flau im Magen", "fr": "mal au ventre", "pt": "enjoo no estômago"},
    "session.felt.cue_q_fired": {"sk": "Sadla hláška?", "en": "Did the cue land?", "ja": "合図は響いた？", "zh": "提示到位吗？", "ru": "Подсказка попала?", "es": "¿Encajó el aviso?", "de": "Hat der Hinweis gepasst?", "fr": "Le signal a-t-il touché ?", "pt": "O aviso acertou?"},
    "session.felt.cue_q_silent": {"sk": "Bola chvíľa, keď sa mala ozvať?", "en": "Was there a moment it should have spoken up?", "ja": "声をかけるべき瞬間はあった？", "zh": "有该出声提醒的时刻吗？", "ru": "Был момент, когда стоило подсказать?", "es": "¿Hubo un momento en que debió avisar?", "de": "Gab es einen Moment, wo er sich hätte melden sollen?", "fr": "Y a-t-il eu un moment où il aurait dû se manifester ?", "pt": "Houve um momento em que devia ter avisado?"},
    "session.felt.cue.landed": {"sk": "sadla", "en": "it landed", "ja": "響いた", "zh": "到位", "ru": "попала", "es": "encajó", "de": "hat gepasst", "fr": "a touché", "pt": "acertou"},
    "session.felt.cue.unneeded": {"sk": "netreba bolo", "en": "wasn't needed", "ja": "不要だった", "zh": "没必要", "ru": "не нужна была", "es": "no hacía falta", "de": "war unnötig", "fr": "pas nécessaire", "pt": "não era preciso"},
    "session.felt.cue.disruptive": {"sk": "rušila", "en": "it disrupted", "ja": "邪魔だった", "zh": "打扰了", "ru": "мешала", "es": "molestó", "de": "hat gestört", "fr": "a gêné", "pt": "atrapalhou"},
    "session.felt.cue.missed": {"sk": "áno, mala", "en": "yes, it should have", "ja": "はい、あった", "zh": "有，该提醒", "ru": "да, стоило", "es": "sí, debió", "de": "ja, hätte sollen", "fr": "oui, il aurait dû", "pt": "sim, devia"},
    "history.export_col.sleep": {"sk": "spánok", "en": "sleep", "ja": "睡眠", "zh": "睡眠", "ru": "сон", "es": "sueño", "de": "Schlaf", "fr": "sommeil", "pt": "sono"},
    "history.export_col.felt_load": {"sk": "vnímaná záťaž", "en": "felt load", "ja": "感じた負荷", "zh": "主观强度", "ru": "ощущ. нагрузка", "es": "carga percibida", "de": "empf. Last", "fr": "charge ressentie", "pt": "carga percebida"},
    "history.export_col.valence": {"sk": "valencia", "en": "valence", "ja": "感情価", "zh": "效价", "ru": "валентность", "es": "valencia", "de": "Valenz", "fr": "valence", "pt": "valência"},
    "history.export_col.body_peak": {"sk": "telo v najintenzívnejšej chvíli", "en": "body at the most intense moment", "ja": "一番きつかったときの体", "zh": "最紧张时的身体", "ru": "тело в самый напряжённый момент", "es": "cuerpo en el momento más intenso", "de": "Körper im intensivsten Moment", "fr": "corps au moment le plus intense", "pt": "corpo no momento mais intenso"},
    "history.export_col.cue_verdict": {"sk": "hláška verdikt", "en": "cue verdict", "ja": "合図の評価", "zh": "提示评价", "ru": "вердикт подсказки", "es": "veredicto aviso", "de": "Hinweis-Urteil", "fr": "verdict signal", "pt": "veredito aviso"},
    "history.export_col.confounded": {"sk": "skreslená?", "en": "confounded?", "ja": "撹乱？", "zh": "受干扰？", "ru": "искажена?", "es": "sesgada?", "de": "verfälscht?", "fr": "faussée ?", "pt": "enviesada?"},
}
for _k, _langs in _DOPLNENE_PREKLADY.items():
    STRINGS.setdefault(_k, {}).update(_langs)

STRINGS.setdefault("app.version_short", {}).update({
    "ja": "アルファ 0.2.1", "zh": "Alpha 0.2.1", "ru": "альфа 0.2.1",
    "es": "alfa 0.2.1", "pt": "alfa 0.2.1",
})

# --- 0.2 B3-worlds: dva svety, jedno telo ----------------------------------
# Hra a praca maju oddelenu historiu, postrehy aj vzhlad; pokojova zakladna
# je spolocna. SK/EN rucne, ostatne jazyky: _tr7 na konci suboru.
# Otazka v dotazniku (hral/pracoval) pouziva existujuce kluce
# `session.context.activity*` - nic nove.
#
# Styri kluce nizsie (hranica vysokeho tepu, prah hlasky) tu maju NOVE
# znenie: od B3-worlds sa rataju len z HERNYCH relacii, takze veta "po
# dalsich N relaciach" by pri pracovnych veceroch klamala. Stare znenia aj
# ich preklady boli zmazane, aby stare znenie neprezilo v ziadnom jazyku.
STRINGS.update({
    'world.play': _sk_en('Hra', 'Play'),
    'world.work': _sk_en('Práca', 'Work'),
    'world.tip': _sk_en(
        'Svet: hra alebo práca — každý má vlastnú históriu a vzhľad.\n'
        'V práci sa ozývam len obrazom. Bežiaca relácia ostáva vo svete, '
        'v ktorom začala.',
        'World: play or work — each keeps its own history and look.\n'
        'At work I only show visual cues. A running session stays in the '
        'world it started in.'),
    'settings.world': _sk_en('Svet', 'World'),
    'settings.world_sub': _sk_en(
        'Hra je Sumi, práca Aizome. Každý svet má vlastnú históriu a postrehy. '
        'V práci sa ozývam len obrazom — bez hlasu a zvuku. Pokojová základňa '
        'je spoločná, telo je jedno; hranicu vysokého tepu aj záťaže počítam '
        'len z hrania.',
        'Play is Sumi, work is Aizome. Each world keeps its own history and '
        'insights. At work I only show visual cues — no voice, no sound. The '
        'resting baseline is shared, it is one body; the high heart-rate and '
        'load limits are learned from play only.'),
    # 0.2 (rebrik): graf ucinnosti rata len hlasky, ktore zazneli - v praci
    # je hlaska len obrazom, takze tam neostalo co ratat.
    'history.world_note': _sk_en(
        'Svet: {world}. Staršie relácie bez štítku patria do Hry. '
        'Graf „{chart}“ ráta len hlášky z hry, ktoré zazneli — v práci sa '
        'ozývam len obrazom.',
        'World: {world}. Older unlabelled sessions count as Play. '
        'The “{chart}” chart counts only play cues that made a sound — at '
        'work I only show a picture.'),
    'ob.step4.title': _sk_en('Vyber si hlavný svet', 'Pick your main world'),
    'ob.step4.body': _sk_en(
        'Prepneš ho kedykoľvek vpravo hore. Každý svet má vlastnú históriu '
        'aj vzhľad.',
        'Switch it any time at the top right. Each world keeps its own history '
        'and look.'),
    'ob.world.play.title': _sk_en('Hra · 墨 Sumi', 'Play · 墨 Sumi'),
    # „väčšinou“: asi desatina hlášok naschvál mlčí (porovnanie) a hláška,
    # ktorej pauza nepríde, je len obrazom — „s hlasom aj obrazom“ sľubovalo
    # viac, než appka robí.
    'ob.world.play.desc': _sk_en(
        'Keď hráš. Hlášky v pauzách, väčšinou s hlasom.\nAtrament so zlatom.',
        'For playing. Cues in the pauses, mostly with voice.\nInk with gold.'),
    'ob.world.work.title': _sk_en('Práca · 藍 Aizome', 'Work · 藍 Aizome'),
    'ob.world.work.desc': _sk_en(
        'Keď pracuješ. Hlášky len obrazom, bez hlasu a zvuku.\nIndigo.',
        'For working. Visual cues only, no voice or sound.\nIndigo.'),
    'session.end.title_work': _sk_en('Pracoval si {time}.', 'You worked for {time}.'),
    'session.end.cues_work': _sk_en(
        'Ozvala som sa {n}× — v práci len obrazom, bez hlasu a zvuku.',
        'I showed up {n} times — at work as a visual only, no voice or sound.'),
    'settings.hr_critical_computed': _sk_en(
        'Tvoja hranica vysokého tepu: {bpm} BPM — spočítané z {n} tvojich '
        'herných relácií. Nenastavuje sa, appka si ju upraví, ako ťa spozná.',
        'Your high heart-rate limit: {bpm} BPM — computed from {n} of your play '
        'sessions. Not a setting; the app adjusts it as it gets to know you.'),
    'settings.hr_critical_learning': _sk_en(
        'Zatiaľ počítam s {bpm} BPM. Vlastnú hranicu ti spočítam po ďalších '
        '{treba} herných reláciách — nemusíš nastavovať nič.',
        'Using {bpm} BPM for now. I will compute your own limit after {treba} '
        'more play sessions — nothing to set.'),
    'cue_rate.computed': _sk_en(
        'Ozvem sa, keď tvoja záťaž drží {hold} s nad {prah} — tú hranicu som si '
        'spočítala z {n} tvojich herných relácií ako úroveň, nad ktorou tráviš '
        'pätinu hrania. Najviac {strop}× za hodinu, odstup aspoň {odstup} min.',
        'I speak when your load holds {hold} s above {prah} — I computed that '
        'line from {n} of your play sessions as the level you spend a fifth of '
        'your playtime above. At most {strop}× per hour, at least {odstup} min '
        'apart.'),
    'cue_rate.learning': _sk_en(
        'Zatiaľ počítam s číslami pre priemerného hráča: ozvem sa, keď záťaž '
        'drží {hold} s nad {prah}. Vlastnú hranicu si spočítam z tvojich '
        'herných relácií — nemusíš nastavovať nič.',
        'For now I use average-player numbers: I speak when load holds {hold} s '
        'above {prah}. I will compute your own line from your play sessions — '
        'nothing to set.'),
})

# --- 0.2 rebrik hlasky: appka sa sama stisi ------------------------------
# hlas -> obraz -> pauza (`rebrik.py`). Jedna ticha veta v Historii, len ked
# je rebrik pod vrcholom, a s dovodom. Appka o sebe v zenskom rode. SK/EN
# rucne, ostatne jazyky: _tr7 na konci suboru.
STRINGS.update({
    'session.felt.cue.agitated': _sk_en('rozhodila ma', 'it wound me up'),
    'history.rebrik.visual': _sk_en(
        'Teraz sa ozývam len obrazom, bez zvuku. {dovod} Zvuk vrátim, keď '
        'ďalšie relácie s hláškou prejdú bez výhrad (treba ešte: {n}).',
        'For now I only show the picture, no sound. {dovod} I will bring the '
        'sound back once more sessions with a cue go by without a complaint '
        '(still needed: {n}).'),
    'history.rebrik.pause': _sk_en(
        'Hlášky mám teraz vypnuté. {dovod} Obrazom to skúsim znova po ďalších '
        'reláciách aspoň na 5 minút (treba ešte: {n}). Ak ti hlášky chýbajú, v '
        'dotazníku po relácii odpovedz „áno, mala“ a od ďalšej relácie to '
        'skúsim znova.',
        'Cues are off for now. {dovod} I will try again with the picture after '
        'more sessions of at least 5 minutes (still needed: {n}). If you miss '
        'them, answer “yes, it should have” in the questionnaire after a '
        'session and I will try again from the next one.'),
    'history.rebrik.why.disruptive': _sk_en(
        'Po relácii si v dotazníku napísal, že hláška rušila.',
        'After a session you said in the questionnaire that the cue got in the way.'),
    'history.rebrik.why.agitated': _sk_en(
        'Po relácii si v dotazníku napísal, že ťa hláška rozhodila.',
        'After a session you said in the questionnaire that the cue wound you up.'),
    'history.rebrik.why.snooze': _sk_en(
        'Do minúty po hláške si ma stíšil a relácia potom ešte pokračovala.',
        'You snoozed me within a minute of a cue, and the session carried on '
        'after that.'),
    'history.rebrik.why.retry': _sk_en(
        'Po pár reláciách ticha to skúšam znova.',
        'After a few quiet sessions I am trying again.'),
    'history.rebrik.why.missed': _sk_en(
        'Napísal si, že som sa mala ozvať, tak to skúšam znova.',
        'You said I should have spoken up, so I am trying again.'),
    'session.end.cues_visual': _sk_en(
        'Ozvala som sa {n}× — len obrazom, bez zvuku.',
        'I showed up {n} times — as a picture only, no sound.'),
    'session.end.none_paused': _sk_en(
        'Hlášky mám po tvojej spätnej väzbe na pár relácií vypnuté — prečo, '
        'nájdeš v Histórii. Ak ti chýbajú, odpovedz nižšie „áno, mala“.',
        'After your feedback I have switched cues off for a few sessions — '
        'History says why. If you miss them, answer “yes, it should have” below.'),
    'kamae.paused_sub': _sk_en(
        'Sledujem tep, ale hlášky mám teraz vypnuté — prečo, nájdeš v Histórii.',
        'Watching your heart rate, but cues are off for now — History says why.'),
})

# --- 0.2 styl hlasky: otazka v onboardingu a riadok v Nastaveniach ---------
# Otazku aj styri odpovede schvalil zadavatel doslovne. Tie iste tri vety
# (bez "neviem") su hodnoty v Nastaveniach -> Zvuk, aby jedna volba nemala
# dve mena. Kicker kroku 1-4 sa zmenil na "z 5" (ich _tr7 riadky zmazane).
# SK/EN rucne, ostatne jazyky: _tr7 na konci suboru.
STRINGS.update({
    'ob.step5.kicker': _sk_en('KROK 5 z 5', 'STEP 5 of 5'),
    'ob.cue.title': _sk_en(
        'Keď ťa hra poriadne vytočí, ako chceš, aby sa appka ozvala?',
        'When a game really winds you up, how do you want the app to speak up?'),
    'ob.cue.voice': _sk_en('Pokojne aj hlasom', 'Voice is fine'),
    'ob.cue.sound': _sk_en('Radšej len zvuk a obrázok',
                           'Rather just a sound and a picture'),
    'ob.cue.visual': _sk_en('Len obrázok, nič nehovor', 'Just a picture, say nothing'),
    'ob.cue.unsure': _sk_en('Neviem, nech si to appka zistí sama',
                            'Not sure, let the app figure it out'),
    'ob.cue.note': _sk_en(
        'Zmeníš to kedykoľvek v Nastaveniach, v časti Zvuk. Keď appke dáš '
        'vedieť, že hlášky prekážajú, stíši sa aj sama — nikdy však nie '
        'hlasnejšie, než tu vyberieš.',
        'You can change this any time in Settings, under Sound. When you tell '
        'the app cues get in the way, it goes quieter on its own — but never '
        'louder than what you pick here.'),
    # Tichy riadok pod otazkou: co z volby "hlasom" odchadza z pocitaca.
    # Rovnaka pravda ako `data.hint`; nazov karty = nav.nastavenia_tabs.zvuk.
    'ob.cue.online_note': _sk_en(
        'Prirodzený hlas je online: texty hlášok (nikdy nie tep) sa pošlú '
        'službe Microsoft na prevod do reči. Hlas z Windows neposiela nič — '
        'prepneš naň v Nastaveniach → Zvuk.',
        'The natural voice is online: the text of your cues (never your heart '
        'rate) is sent to Microsoft to be turned into speech. The Windows voice '
        'sends nothing — switch to it in Settings → Sound.'),
    'settings.cue_style': _sk_en('Ako sa ozývam', 'How I speak up'),
    'settings.cue_style_sub': _sk_en(
        'Keď mi dáš vedieť, že hlášky prekážajú, stíšim sa aj sama — nikdy '
        'však nie hlasnejšie, než tu vyberieš. V práci sa ozývam len obrazom.',
        'When you tell me cues get in the way, I go quieter on my own — but '
        'never louder than what you pick here. At work I only show a picture.'),
})

# --- 0.2 ovladac: vstup bez jedinej pauzy -----------------------------------
# Gyroskop ovladaca alebo pacicka bez mrtvej zony hlasi Windowsu vstup bez
# prestania a appka nenajde pauzu (odmerane u zadavatela). Tichy riadok na
# Dnes raz za relaciu (`_tick_nonstop_input`) a tip v navode k parovaniu.
# Rovnaka rada ako `session.end.none_nopause`. SK/EN rucne, ostatne
# jazyky: _tr7 na konci suboru.
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
        'prestávky a appka nenájde pauzu, v ktorej by sa ozvala.',
        'Playing with a controller? Turn off its gyro (motion sensor) if you '
        "don't use it, and give the sticks a small deadzone. Otherwise it may "
        'report input nonstop and the app finds no pause to speak up in.'),
})

# --- 24. 9. rozhodnutia zadavatela -------------------------------------------
# "Teraz nie" stisi len hlasky a meria sa dalej (stav v strede stranky Dnes).
# Ukazka "Ako to znie" ide za stylom hlasky - veta pod nou hovori, co naozaj
# urobi. SK/EN rucne, ostatne jazyky: _tr7 na konci suboru.
STRINGS.update({
    'kamae.snoozed': _sk_en('Mlčím', 'Keeping quiet'),
    'kamae.snoozed_sub': _sk_en(
        '„Teraz nie“ platí do {until} — dovtedy sa neozvem, tep však merám '
        'ďalej. Skôr to zrušíš tou istou skratkou.',
        '“Not now” holds until {until} — I won’t speak up till then, but I '
        'keep measuring your heart rate. The same shortcut ends it sooner.'),
    'settings.preview_sub_sound': _sk_en(
        'Prehrá zvuk prvej pripomienky tak, ako zaznie v hre, a ukáže jej '
        'obrázok. Bez slov — tak si to vybral v „Ako sa ozývam“.',
        'Plays the first reminder’s sound the way it will sound in-game and '
        'shows its picture. No words — that is what you chose under “How I '
        'speak up”.'),
    'settings.preview_sub_visual': _sk_en(
        'Vybral si len obrázok, takže v hre nič nezaznie — hláška sa len '
        'ukáže. Tlačidlo ukáže obrázok prvej pripomienky.',
        'You chose just a picture, so nothing plays in-game — the cue is only '
        'shown. The button shows the first reminder’s picture.'),
    # Ukazka v style "zvuk"/"obraz", ked ziadna zapnuta pripomienka nema
    # obrazok v hre - v hre by vtedy neprisla ziadna hlaska.
    'log.preview_no_picture': _sk_en(
        'Ukážka: žiadna zapnutá pripomienka nemá zapnutý obrázok v hre, takže '
        'v tomto štýle by som sa v hre neozvala vôbec.',
        'Preview: no enabled reminder has its in-game picture turned on, so in '
        'this style I would not show up in-game at all.'),
    # Dotaznik po relacii bez hlasky, v ktorej platilo "teraz nie" - vtedy
    # automat spal a ostatne vety o ticho by mohli klamat (`_preco_ticho`).
    'session.end.none_snoozed': _sk_en(
        '{min} min z relácie platilo tvoje „teraz nie“ — vtedy som mlčala, ako '
        'si chcel.',
        'Your “not now” was on for {min} min of this session — I kept quiet '
        'then, as you asked.'),
})

# --- × v titulkovej liste (0.2) ----------------------------------------------
# Krizik appku neukonci, len ju schova do listy - port pre telefon ostava
# otvoreny a tep sa dalej meria. Prvy raz to appka povie a da na vyber
# (`DandurfApp.on_close`). SK/EN rucne, ostatnych 7 jazykov pride vo faze
# jazykov.
STRINGS.update({
    'tray.close_first': _sk_en(
        'Bežím ďalej v lište (ikona pri hodinách). Kým je zapnuté „Počúvať '
        'tep z hodiniek“, port {port} ostáva otvorený pre telefón, a kým som '
        'spustená (▶ na stránke Dnes), tep ďalej meriam a ukladám. Úplne ma '
        'vypneš pravým klikom na ikonu v lište → Ukončiť.\n\n'
        'Nechať ma bežať v lište? (Nie = ukončiť hneď)',
        'I keep running in the tray (the icon by the clock). While “Listen '
        'for heart rate from the watch” is on, port {port} stays open for '
        'your phone, and while I’m started (▶ on the Today page), I keep '
        'measuring and saving your heart rate. To quit me completely, '
        'right-click the tray icon → Quit.\n\n'
        'Keep me running in the tray? (No = quit now)'),
})

# --- paleta prikazov (Ctrl+K) a veta o prekladoch (0.2, faza jazykov) -------
# Paleta mala texty natvrdo po slovensky (`_command_palette_items`,
# `ui_shell.CommandPalette`) - anglicky hrac v nej videl „Navigácia“ a
# „Pomoc“. Polozka sprievodcu sa vola ako jeho panel (guide.panel_title).
# Veta pod vyberom jazyka hovori, co je zdroj a co preklad; ukazuje sa vo
# vsetkych jazykoch. SK/EN rucne, ostatne jazyky: _tr7 na konci suboru.
STRINGS.update({
    'palette.placeholder': _sk_en('Napíš názov stránky, profilu alebo hlášky…',
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
# 0.2 FAZA JAZYKOV - preklad klucov z `_sk_en` do ja / zh / ru / es / de /
# fr / pt
# ==========================================================================
#
# Kluce so sk/en rucne (`_sk_en`) mali ostatnych 7 jazykov po anglicky -
# tu je ich preklad (zdroj je SK, EN pomaha s vyznamom). Kluce, ktore su
# v STRINGS ako plny slovnik, maju preklad priamo v nom a
# `history.export_extra` ma opraveny riadok v davke vyssie (predtym doslovne
# lomitko+n namiesto noveho riadku). Ziadny z tychto klucov nema iny
# `_tr7` riadok, aby stary preklad nemohol potichu prezit pod novym.
#
# Preklady su s pomocou AI (Claude) a rodeny hovoriaci ich este
# nekontroloval (`settings.language_note`).

_tr7('settings.auto_profile', '知っているゲームなら、自分でプロファイルを切り替えて監視を始めます', '遇到我认识的游戏时，我会自己切换配置文件并开始监听', 'Когда идёт знакомая мне игра, сама переключаю профиль и начинаю слушать', 'Con un juego que conozco, cambio yo sola el perfil y empiezo a escuchar', 'Bei einem bekannten Spiel wechsle ich selbst das Profil und starte das Zuhören', 'Avec un jeu que je connais, je change de profil et lance l’écoute toute seule', 'Com um jogo que eu conheço, troco o perfil e começo a ouvir sozinha')
_tr7('slots.hint', 'いつ声をかけるかは、あなたの体が決めます — アプリは負荷がしばらく高いまま続くのを待ち、負荷がもう上がっていない合間に声をかけます。心拍が「ピーク」の帯にある間は黙っています。ここでは、何を言うかを設定します。「音声＋効果音」は両方を鳴らします。', '什么时候出声，由你的身体决定——应用会等负荷持续偏高一阵子，然后在负荷不再上升的间歇里出声；心率处于高峰区间时，它保持安静。在这里设置它具体说什么。“语音 + 音效”会两者都播放。', 'Когда подать голос, решает твоё тело — приложение ждёт, пока нагрузка какое-то время продержится высокой, и подаёт голос в паузе, когда нагрузка уже не растёт; пока пульс в пиковой зоне, оно молчит. Здесь ты настраиваешь, что именно оно скажет. «Голос + звук» проигрывает и то и другое.', 'Cuándo habla lo decide tu cuerpo — la app espera a que tu carga se mantenga alta un rato y habla en una pausa, cuando la carga ya no sube; mientras el pulso está en la zona de pico, guarda silencio. Aquí ajustas qué dice exactamente. «Voz + sonido» reproduce ambos.', 'Wann sich die App meldet, entscheidet dein Körper — sie wartet, bis deine Last eine Weile oben bleibt, und meldet sich in einer Pause, wenn die Last nicht mehr steigt; solange dein Puls im Spitzenbereich ist, schweigt sie. Hier stellst du ein, was sie genau sagt. „Stimme + Ton“ spielt beides ab.', 'C’est ton corps qui décide quand l’app se manifeste — elle attend que ta charge reste haute un moment, puis se manifeste pendant une pause, quand la charge ne monte plus ; tant que ton pouls est en zone de pic, elle se tait. Ici, tu règles ce qu’elle dit exactement. « Voix + son » joue les deux.', 'Quando avisar, quem decide é o seu corpo — o app espera até a sua carga se manter alta por um tempo e avisa numa pausa, quando a carga já não está subindo; enquanto o pulso está na zona de pico, fica em silêncio. Aqui você define o que exatamente ele diz. “Voz + som” toca os dois.')
_tr7('hr.step2_body', 'Android / Wear OS：Google Play の「HeartRateOnStream for OBS」（無料）。iPhone / Apple Watch：App Store の「PulseOSC」（有料）— OSC を送信し、アプリのコードはそれを受信できますが、iPhone 経由の方法はまだ試されていません。作者が Apple の端末を持っていないからです。試したら、うまくいったか教えてください。次の手順のパスワード、シーン、ソースは Android 用アプリだけに関係します。PulseOSC では IP とポートを入力するだけです。下のコードを読み取って、アプリを時計とつないでください。', 'Android / Wear OS：Google Play 上的“HeartRateOnStream for OBS”（免费）。iPhone / Apple Watch：App Store 上的“PulseOSC”（付费）——它发送 OSC，应用的代码能够接收，但 iPhone 这条路目前还没有测试过：作者没有 Apple 设备。如果你试了，请告诉作者能不能用。后面步骤里的密码、场景和来源只适用于 Android 应用；在 PulseOSC 里只需填写 IP 和端口。扫描下方的二维码，把应用和手表连接起来。', 'Android / Wear OS: «HeartRateOnStream for OBS» из Google Play (бесплатно). iPhone / Apple Watch: «PulseOSC» из App Store (платно) — отправляет OSC, и код приложения умеет его принимать, но путь через iPhone пока не проверен: у автора нет устройства Apple. Если попробуешь, дай знать, работает ли у тебя. Пароль, сцена и источник в следующих шагах касаются только приложения для Android; в PulseOSC вводишь только IP и порт. Отсканируй код ниже и подключи приложение к часам.', 'Android / Wear OS: «HeartRateOnStream for OBS» de Google Play (gratis). iPhone / Apple Watch: «PulseOSC» de la App Store (de pago) — envía OSC y el código de la app puede recibirlo, pero la vía con iPhone aún no se ha probado: el autor no tiene ningún dispositivo de Apple. Si la pruebas, cuéntame si te funciona. La contraseña, la escena y la fuente de los pasos siguientes solo se refieren a la app para Android; en PulseOSC solo introduces la IP y el puerto. Escanea el código de abajo y conecta la app con tu reloj.', 'Android / Wear OS: „HeartRateOnStream for OBS“ aus Google Play (kostenlos). iPhone / Apple Watch: „PulseOSC“ aus dem App Store (kostenpflichtig) — sie sendet OSC, und der Code der App kann es empfangen, aber der Weg über das iPhone ist bisher nicht ausprobiert: Der Autor hat kein Gerät von Apple. Wenn du es ausprobierst, sag Bescheid, ob es bei dir läuft. Passwort, Szene und Quelle in den nächsten Schritten gelten nur für die Android-App; in PulseOSC trägst du nur IP und Port ein. Scanne unten einen Code und verbinde die App mit der Uhr.', 'Android / Wear OS : « HeartRateOnStream for OBS » sur Google Play (gratuit). iPhone / Apple Watch : « PulseOSC » sur l’App Store (payant) — elle envoie de l’OSC et le code de l’app sait le recevoir, mais la voie par iPhone n’a pas encore été testée : l’auteur n’a pas d’appareil Apple. Si tu l’essaies, dis-moi si ça marche chez toi. Le mot de passe, la scène et la source des étapes suivantes ne concernent que l’app Android ; dans PulseOSC, tu saisis seulement l’IP et le port. Scanne un code ci-dessous et connecte l’app à ta montre.', 'Android / Wear OS: “HeartRateOnStream for OBS” no Google Play (grátis). iPhone / Apple Watch: “PulseOSC” na App Store (pago) — ele envia OSC e o código do app consegue recebê-lo, mas o caminho pelo iPhone ainda não foi testado: o autor não tem nenhum aparelho da Apple. Se você testar, conte se funcionou. A senha, a cena e a fonte dos próximos passos valem só para o app de Android; no PulseOSC você só informa o IP e a porta. Escaneie um código abaixo e conecte o app ao relógio.')
_tr7('history.empty', 'まだセッションがありません。「ゲーム中」ページで「時計から心拍を受け取る」をオンにし、「今日」ページの ▶ でアプリを開始して、少なくとも1分プレイしてください — 停止すると、セッションがここに表示されます。', '还没有记录。在“游戏中”页面打开“接收手表的心率”，在“今天”页面用 ▶ 启动应用，然后至少玩一分钟——停止后，这次记录就会出现在这里。', 'Сессий пока нет. На странице «В игре» включи «Слушать пульс с часов», запусти приложение кнопкой ▶ на странице «Сегодня» и поиграй хотя бы минуту — после остановки сессия появится здесь.', 'Todavía no hay ninguna sesión. En la página «En el juego» activa «Escuchar el pulso del reloj», inicia la app con el botón ▶ de la página Hoy y juega al menos un minuto — cuando la detengas, la sesión aparecerá aquí.', 'Noch keine Sitzung. Schalte auf der Seite „Im Spiel“ „Puls von der Uhr empfangen“ ein, starte die App mit ▶ auf der Seite Heute und spiel mindestens eine Minute — nach dem Stoppen erscheint die Sitzung hier.', 'Pas encore de séance. Sur la page « En jeu », active « Écouter le pouls de la montre », lance l’app avec ▶ sur la page Aujourd’hui et joue au moins une minute — une fois l’app arrêtée, la séance apparaît ici.', 'Nenhuma sessão ainda. Na página “No jogo”, ative “Ouvir o pulso do relógio”, inicie o app com ▶ na página Hoje e jogue pelo menos um minuto — quando você parar, a sessão aparece aqui.')
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
_tr7('metric.load.more', '負荷のバーは、心拍から実際にわかる3つのことを組み合わせています。安静時よりどれだけ上か、どれだけ速く上がっているか、どれだけ長く高いままか。安静時の値は今夜だけでなく、あなたの穏やかだった夜からも取ります — 今日は高めから始まっている（コーヒー、暑さ、疲れ）なら、バーはゲームだけでなくそれも映します。バーの上の言葉は、今この瞬間の心拍の位置だけを示します。「やや上昇」は安静時より 10 BPM 上から、「高い」は 25 BPM から、「ピーク」はあなたの高心拍のしきい値からです。アプリにあなたのセッションが十分たまるまでは、安静時の値は今夜だけから取り、平均的なプレイヤー向けのしきい値を使います。この言葉が合図を出すわけではありません。負荷が「トリガー」ページのしきい値を超えると、アプリはまずそれがしばらく続くかを数え、そのあとで、負荷がもう上がっていないゲームの合間を待ちます。言葉が「ピーク」を示している間、アプリは黙っています。これは HRV でも診断でもありません。', '负荷条由心率真正能看出来的三件事组成：你比平静水平高多少、心率上升多快、在高位停留多久。平静水平取自你较平静的那些晚上，而不只是今晚——如果你今天的起点就偏高（咖啡、炎热、疲劳），负荷条也会显示出来，而不只反映游戏。负荷条上方的词只说明你的心率此刻处在哪里：“略高”从比平静水平高 10 BPM 开始，“偏高”从高 25 BPM 开始，“高峰”则从你的高心率阈值开始。在应用积累足够多你的记录之前，平静水平只取今晚的数据，阈值则用普通玩家的数值。这个词不会触发提示：当负荷越过“触发器”页面上的负荷阈值时，应用会先计时，看它能否在那里停留一阵子，然后才等待游戏中负荷不再上升的间歇。这个词显示“高峰”时，应用保持安静。这不是 HRV，也不是诊断。', 'Полоса нагрузки складывается из трёх вещей, которые по пульсу действительно можно определить: насколько ты выше покоя, как быстро растёт пульс и как долго он держится наверху. Покой приложение берёт из твоих более спокойных вечеров, а не только из сегодняшнего — если сегодня ты начинаешь выше (кофе, жара, усталость), полоса покажет и это, а не только игру. Слово над полосой говорит только о том, где твой пульс прямо сейчас: «Повышенная» — от 10 BPM выше покоя, «Высокая» — от 25 BPM, а «Пик» — от твоего порога высокого пульса. Пока у приложения мало твоих сессий, покой оно берёт только из сегодняшнего вечера, а порог — для среднего игрока. Слово подсказку не запускает: когда нагрузка переходит порог со страницы «Триггеры», приложение сначала считает, продержится ли она там какое-то время, и только потом ждёт паузы в игре, в которой нагрузка уже не растёт. Пока слово показывает «Пик», приложение молчит. Это не HRV и не диагноз.', 'La barra de carga combina tres cosas que el pulso sí permite saber: cuánto estás por encima de tu reposo, lo rápido que sube el pulso y cuánto tiempo se mantiene alto. Tu reposo la app lo toma de tus noches más tranquilas, no solo de la de hoy — si hoy empiezas más alto (café, calor, cansancio), la barra también lo mostrará, no solo el juego. La palabra sobre la barra solo indica dónde está tu pulso ahora mismo: «Elevada» empieza 10 BPM por encima de tu reposo, «Alta» a partir de 25 BPM y «Pico» a partir de tu límite de pulso alto. Mientras la app no tenga suficientes sesiones tuyas, toma el reposo solo de la noche de hoy y usa el límite de un jugador medio. La palabra no dispara el aviso: cuando la carga supera el umbral de la página Disparadores, la app primero cuenta si se mantiene ahí un rato, y solo entonces espera una pausa en el juego en la que la carga ya no suba. Mientras la palabra dice «Pico», la app guarda silencio. No es HRV ni un diagnóstico.', 'Der Lastbalken setzt sich aus drei Dingen zusammen, die sich aus dem Puls wirklich ablesen lassen: wie weit du über deiner Ruhe bist, wie schnell der Puls steigt und wie lange er oben bleibt. Deine Ruhe nimmt die App aus deinen ruhigeren Abenden, nicht nur aus dem heutigen — wenn du heute höher startest (Kaffee, Hitze, Müdigkeit), zeigt der Balken auch das, nicht nur das Spiel. Das Wort über dem Balken sagt nur, wo dein Puls gerade steht: „Erhöht“ gilt ab 10 BPM über deiner Ruhe, „Hoch“ ab 25 BPM und „Spitze“ ab deiner Grenze für hohen Puls. Solange die App nicht genug Sitzungen von dir hat, nimmt sie die Ruhe nur aus dem heutigen Abend und die Grenze eines durchschnittlichen Spielers. Das Wort löst keinen Hinweis aus: Wenn die Last die Schwelle von der Seite Trigger überschreitet, zählt die App zuerst, ob sie eine Weile dort bleibt, und wartet erst dann auf eine Pause im Spiel, in der die Last nicht mehr steigt. Solange das Wort „Spitze“ zeigt, schweigt die App. Das ist weder HRV noch eine Diagnose.', 'La barre de charge combine trois choses que le pouls permet vraiment de savoir : de combien tu es au-dessus de ton niveau de repos, à quelle vitesse ton pouls monte et combien de temps il reste haut. Ton niveau de repos, l’app le tire de tes soirées plus calmes, pas seulement de celle d’aujourd’hui — si tu commences plus haut aujourd’hui (café, chaleur, fatigue), la barre le montre aussi, pas seulement le jeu. Le mot au-dessus de la barre dit seulement où se trouve ton pouls en ce moment : « Élevée » commence à 10 BPM au-dessus de ton niveau de repos, « Haute » à 25 BPM et « Pic » à ton seuil de pouls élevé. Tant que l’app n’a pas assez de tes séances, elle prend ton niveau de repos de ce soir seulement, et un seuil pour un joueur moyen. Le mot ne déclenche pas le rappel : quand la charge franchit le seuil de la page Déclencheurs, l’app compte d’abord si elle s’y maintient un moment, et seulement ensuite attend une pause dans le jeu où la charge ne monte plus. Tant que le mot affiche « Pic », l’app se tait. Ce n’est ni la VFC ni un diagnostic.', 'A barra de carga combina três coisas que dá para saber de verdade pelo pulso: quanto você está acima do repouso, com que rapidez o pulso sobe e por quanto tempo fica alto. O repouso o app tira das suas noites mais calmas, não só da de hoje — se hoje você começa mais alto (café, calor, cansaço), a barra mostra isso também, não só o jogo. A palavra acima da barra fala apenas de onde o seu pulso está agora: “Elevada” começa 10 BPM acima do repouso, “Alta” a partir de 25 BPM e “Pico” a partir do seu limite de pulso alto. Enquanto o app não tem sessões suas suficientes, tira o repouso só da noite de hoje e usa um limite de jogador médio. A palavra não dispara o aviso: quando a carga passa o limiar da página Gatilhos, o app primeiro conta se ela se mantém ali por um tempo, e só depois espera uma pausa no jogo em que a carga já não esteja subindo. Enquanto a palavra mostra “Pico”, o app fica em silêncio. Não é HRV nem diagnóstico.')
_tr7('metric.hrr.more', '緊張した場面のあと、どれだけ速く下がってくるかのおおまかな目安です。下がり幅が大きい = 早く平静に戻る。ふつうのゲーム中のピークから算出するもので、運動負荷テストではありません — 体力の成績ではなく、時間を通じた自分自身の傾向として見てください。', '粗略反映你在紧张之后多快回落。下降越多 = 越快回到平静。它是根据普通的游戏峰值计算的，不是运动负荷测试——把它当作你自己随时间变化的趋势，而不是体能评分。', 'Приблизительная картина того, как быстро ты возвращаешься вниз после напряжения. Больший спад = быстрее обратно к покою. Считается по обычным игровым пикам, а не по нагрузочному тесту — воспринимай это как свой собственный тренд во времени, а не как оценку физической формы.', 'Una imagen aproximada de lo rápido que vuelves a bajar después de un momento de tensión. Una caída mayor = vuelta más rápida a la calma. Se calcula a partir de los picos normales del juego, no de una prueba de esfuerzo — tómalo como tu propia tendencia en el tiempo, no como una nota de tu forma física.', 'Ein grobes Bild davon, wie schnell du nach einer Anspannung wieder runterkommst. Größerer Abfall = schneller zurück zur Ruhe. Berechnet aus gewöhnlichen Spitzen beim Spielen, nicht aus einem Belastungstest — sieh es als deinen eigenen Trend über die Zeit, nicht als Note für deine Fitness.', 'Une image approximative de la vitesse à laquelle tu redescends après un moment intense. Une plus grande baisse = retour au calme plus rapide. Le calcul part des pics de jeu ordinaires, pas d’un test d’effort — vois-y ta propre tendance dans le temps, pas une note de forme.', 'Uma ideia aproximada de quão rápido você volta a descer depois de um momento tenso. Queda maior = volta mais rápida à calma. É calculado a partir de picos comuns de jogo, não de um teste de esforço — encare como a sua própria tendência ao longo do tempo, não como nota de condicionamento físico.')
_tr7('metric.zones.more', 'ヘッドショットのあとの短いピークはふつうのことです。しきい値を超えている時間が長いなら、ゲームがあなたを緊張させ続けているのかもしれません。', '爆头后的短暂峰值很正常。长时间处于阈值以上，可能说明游戏让你一直处于紧绷状态。', 'Короткие пики после хедшота — это нормально. Долгое время выше порога может значить, что игра держит тебя в напряжении.', 'Los picos breves después de un headshot son normales. Mucho tiempo por encima del límite puede significar que el juego te mantiene en tensión.', 'Kurze Spitzen nach einem Headshot sind normal. Lange Zeit über der Grenze kann bedeuten, dass dich das Spiel unter Spannung hält.', 'De courts pics après un headshot sont normaux. Beaucoup de temps au-dessus du seuil peut vouloir dire que le jeu te maintient sous tension.', 'Picos curtos depois de um headshot são normais. Muito tempo acima do limite pode significar que o jogo te mantém em tensão.')
_tr7('dashboard.picker_hint', '「今日」にはカードが4枚入ります。カードを別のカードにドラッグすると、場所が入れ替わります。', '“今天”页面能放 4 张卡片。把一张卡片拖到另一张上即可调整顺序——两者会互换位置。', 'На «Сегодня» помещаются 4 карточки. Порядок меняешь, перетаскивая карточку на другую, — они поменяются местами.', 'En Hoy caben 4 tarjetas. Cambia el orden arrastrando una tarjeta sobre otra — intercambian su lugar.', 'Auf Heute passen 4 Karten. Die Reihenfolge änderst du, indem du eine Karte auf eine andere ziehst — sie tauschen die Plätze.', 'La page Aujourd’hui a de la place pour 4 cartes. Pour changer l’ordre, fais glisser une carte sur une autre — elles échangent leur place.', 'Cabem 4 cartões em Hoje. Para mudar a ordem, arraste um cartão sobre outro — eles trocam de lugar.')
_tr7('metric.over.more', '心拍が高心拍のしきい値を超えていた時間。このしきい値は設定するものではありません — アプリがあなたのセッションから算出し、少しずつ微調整します（「ゲーム中」ページの「時計と心拍」カードで確認できます）。成績ではありません — 短いピークはゲームにつきものです。意味があるのは、同じくらいのプレイ時間なのに、数字が夜ごとに増えていくときです — そのときは、その夜に何が変わったのかを振り返ってみてください。', '你的心率在高心率阈值以上待了多久。这个阈值不用你设置——应用根据你的记录计算，并慢慢微调（可以在“游戏中”页面的“手表与心率”卡片里看到）。这不是评分——短暂的峰值本来就是游戏的一部分。值得留意的是，在游戏时长相同的情况下，这个数字一晚比一晚高——那时可以看看那几个晚上有什么变化。', 'Сколько времени твой пульс провёл выше порога высокого пульса. Его ты не настраиваешь — приложение вычисляет его по твоим сессиям и понемногу уточняет (он виден на странице «В игре», в карточке «Часы и пульс»). Это не оценка: короткие пики — часть игры. Интересно становится, когда число растёт вечер за вечером при одинаково долгой игре, — тогда попробуй посмотреть, что в эти вечера изменилось.', 'Cuánto tiempo pasó tu pulso por encima del límite de pulso alto. Ese límite no lo ajustas tú — la app lo calcula a partir de tus sesiones y lo va afinando poco a poco (lo ves en la página «En el juego», en la tarjeta «Reloj y pulso»). No es una nota — los picos breves forman parte del juego. Lo interesante es cuando el número crece noche tras noche con el mismo tiempo de juego — entonces fíjate en qué cambió esas noches.', 'Wie lange dein Puls über deiner Grenze für hohen Puls lag. Die stellst du nicht ein — die App berechnet sie aus deinen Sitzungen und stimmt sie langsam fein ab (du siehst sie auf der Seite „Im Spiel“ in der Karte „Uhr und Puls“). Das ist keine Note — kurze Spitzen gehören zum Spielen. Interessant wird es, wenn die Zahl Abend für Abend bei gleich langem Spielen wächst — dann schau, was sich an diesen Abenden verändert hat.', 'Combien de temps ton pouls a passé au-dessus de ton seuil de pouls élevé. Tu ne le règles pas — l’app le calcule à partir de tes séances et l’affine lentement (tu le vois sur la page « En jeu », dans la carte « Montre et pouls »). Ce n’est pas une note — les pics courts font partie du jeu. Ça devient intéressant quand le chiffre augmente soir après soir pour une même durée de jeu — regarde alors ce qui a changé ces soirs-là.', 'Quanto tempo o seu pulso passou acima do seu limite de pulso alto. Você não o define — o app o calcula a partir das suas sessões e o ajusta aos poucos (você o vê na página “No jogo”, no cartão “Relógio e pulso”). Não é uma nota — picos curtos fazem parte do jogo. Fica interessante quando o número cresce noite após noite com o mesmo tempo de jogo — aí vale olhar o que mudou nessas noites.')
_tr7('metric.breath.title', 'アプリからの合図', '应用发出的提示', 'Подсказки от приложения', 'Avisos de la app', 'Hinweise der App', 'Rappels de l’app', 'Avisos do app')
_tr7('metric.breath.short', 'このセッションでアプリが自分から出した合図の数 — 負荷がしばらく高いまま続いたときに。', '本次记录中应用主动给了你多少条提示——在你的负荷持续偏高一阵子的时候。', 'Сколько подсказок приложение подало тебе в этой сессии само — когда нагрузка какое-то время держалась высокой.', 'Cuántos avisos te dio la app por sí sola en esta sesión — cuando tu carga se mantuvo alta un rato.', 'Wie viele Hinweise dir die App in dieser Sitzung von selbst gegeben hat — wenn deine Last eine Weile oben blieb.', 'Combien de rappels l’app t’a envoyés d’elle-même pendant cette séance — quand ta charge est restée haute un moment.', 'Quantos avisos o app te deu por conta própria nesta sessão — quando a sua carga ficou alta por um tempo.')
_tr7('metric.breath.more', '合図は4種類のうちのひとつ — 重心、顎、脱力、呼吸 — で、アプリはオンにしているものを順番に出します。数えるのは、負荷がしばらく高いまま続いたときにアプリが自分から出したものだけで、「テスト」ボタンで試したものは含みません。音なしで、ビジュアルだけで来た合図も含みます。', '每条提示是四种之一——重心、下颌、放松或呼吸——应用会在你打开的那几种之间轮换。只统计应用在你负荷持续偏高一阵子时主动发出的提示；你用“测试”按钮试的不算。只以视觉效果出现、没有声音的提示也算在内。', 'Подсказка — одна из четырёх: центр тяжести, челюсть, расслабление или дыхание, — и приложение чередует те, что у тебя включены. Считаются только те, что оно подало само, когда нагрузка какое-то время держалась высокой; твои пробы кнопкой «Тест» не засчитываются. Сюда входят и подсказки, пришедшие только визуалом, без звука.', 'Un aviso es uno de cuatro — centro, mandíbula, soltar o respiración — y la app va alternando los que tienes activados. Solo cuentan los que dio por sí sola, cuando tu carga se mantuvo alta un rato; tus pruebas con el botón «Probar» no cuentan. También cuentan los avisos que llegaron solo como visual, sin sonido.', 'Ein Hinweis ist einer von vier — Schwerpunkt, Kiefer, Lösen oder Atem — und die App wechselt zwischen denen ab, die du eingeschaltet hast. Gezählt wird nur, was sie von selbst gegeben hat, als deine Last eine Weile oben blieb; deine eigenen Versuche mit dem Knopf „Testen“ zählen nicht. Dazu gehören auch Hinweise, die nur als Visual kamen, ohne Ton.', 'Un rappel est l’un des quatre — ancrage, mâchoire, relâche ou respiration — et l’app alterne ceux que tu as activés. Ne comptent que ceux qu’elle a envoyés d’elle-même, quand ta charge est restée haute un moment ; tes essais avec le bouton « Tester » ne comptent pas. Les rappels arrivés seulement en visuel, sans son, comptent aussi.', 'Um aviso é um de quatro — centro, mandíbula, soltar ou respiração — e o app alterna entre os que você deixou ativados. Só conta o que ele deu por conta própria, quando a sua carga ficou alta por um tempo; os seus testes com o botão “Testar” não contam. Contam também os avisos que vieram só como visual, sem som.')
_tr7('metric.week.short', '今週このワールドで何回セッションがあり、合計でどれだけの時間だったか。', '本周你在这个世界里有多少次记录，总共多长时间。', 'Сколько сессий у тебя было на этой неделе в этом мире и сколько это времени в сумме.', 'Cuántas sesiones has tenido esta semana en este mundo y cuánto tiempo sumaron en total.', 'Wie viele Sitzungen du diese Woche in dieser Welt hattest und wie viel Zeit das insgesamt war.', 'Combien de séances tu as eues cette semaine dans ce monde, et combien de temps cela fait au total.', 'Quantas sessões você teve esta semana neste mundo e quanto tempo isso deu no total.')
_tr7('metric.week.more', '週は月曜日から数え、今いるワールド（ゲームまたは仕事）のセッションだけを数えます。今週アプリがどれだけ記録したかを見渡すためだけのものです。', '一周从周一算起，只统计你当前所在世界（游戏或工作）的记录。它只是让你大致了解应用本周记录了多少。', 'Неделя считается с понедельника, и учитываются только сессии мира, в котором ты сейчас (Игра или Работа). Это просто обзор того, сколько приложение записало за эту неделю.', 'La semana se cuenta desde el lunes y solo cuentan las sesiones del mundo en el que estás ahora (Juego o Trabajo). Sirve solo para ver cuánto ha registrado la app esta semana.', 'Die Woche zählt ab Montag, und es zählen nur Sitzungen der Welt, in der du gerade bist (Spiel oder Arbeit). Sie dient nur als Überblick, wie viel die App diese Woche aufgezeichnet hat.', 'La semaine commence le lundi, et seules comptent les séances du monde où tu te trouves (Jeu ou Travail). C’est juste un aperçu de ce que l’app a enregistré cette semaine.', 'A semana conta a partir de segunda-feira, e só entram as sessões do mundo em que você está agora (Jogo ou Trabalho). Serve só como visão geral de quanto o app registrou esta semana.')
_tr7('metric.session_len.title', 'セッションの長さ', '记录时长', 'Длина сессии', 'Duración de la sesión', 'Sitzungslänge', 'Durée de la séance', 'Duração da sessão')
_tr7('metric.session_len.short', 'セッションがどれだけ続いているか — アプリが監視を始めてから。', '本次记录持续了多久——从应用开始监听算起。', 'Сколько длится сессия — с тех пор как приложение начало слушать.', 'Cuánto dura la sesión — desde que la app empezó a escuchar.', 'Wie lange die Sitzung dauert — seit die App angefangen hat zuzuhören.', 'Depuis combien de temps dure la séance — depuis que l’app a commencé à écouter.', 'Há quanto tempo a sessão dura — desde que o app começou a ouvir.')
_tr7('metric.session_len.more', 'セッションはゲームを起動したときではなく、アプリが監視を始めたときに始まり、監視をやめたときに終わります。ただの時計であって、評価ではありません。長いセッションが悪いわけでも、短いセッションが良いわけでもありません。アプリが今監視していないときは、カードに「—」が表示されます。', '记录从应用开始监听时算起，而不是从你启动游戏时算起，在它停止监听时结束。这只是一个计时，不是评价：长的记录不代表不好，短的也不代表好。应用当前没有在监听时，卡片会显示“—”。', 'Сессия начинается, когда приложение начинает слушать, а не когда ты запускаешь игру, и заканчивается, когда оно перестаёт слушать. Это просто часы, а не оценка: долгая сессия — не плохо, а короткая — не хорошо. Когда приложение сейчас не слушает, карточка показывает «—».', 'La sesión empieza cuando la app empieza a escuchar, no cuando abres el juego, y termina cuando deja de escuchar. Solo mide tiempo, no es una valoración: una sesión larga no es mala y una corta no es buena. Cuando la app no está escuchando, la tarjeta muestra «—».', 'Eine Sitzung beginnt, wenn die App anfängt zuzuhören, nicht wenn du das Spiel startest, und endet, wenn sie aufhört zuzuhören. Das ist nur eine Zeitmessung, keine Bewertung: Eine lange Sitzung ist nicht schlecht und eine kurze nicht gut. Wenn die App gerade nicht zuhört, zeigt die Karte „—“.', 'Une séance commence quand l’app se met à écouter, pas quand tu lances le jeu, et se termine quand elle arrête d’écouter. C’est juste une horloge, pas une évaluation : une longue séance n’est pas mauvaise et une courte n’est pas bonne. Quand l’app n’écoute pas, la carte affiche « — ».', 'A sessão começa quando o app começa a ouvir, não quando você abre o jogo, e termina quando ele para de ouvir. É só um relógio, não uma avaliação: sessão longa não é ruim e sessão curta não é boa. Quando o app não está ouvindo, o cartão mostra “—”.')
_tr7('metric.last_cue.title', '最後の合図から', '距上次提示', 'С последней подсказки', 'Desde el último aviso', 'Seit dem letzten Hinweis', 'Depuis le dernier rappel', 'Desde o último aviso')
_tr7('metric.last_cue.short', 'このセッションでアプリが自分から出した最後の合図から、何分たったか。', '距离本次记录中应用上一次主动给你的提示，过去了多少分钟。', 'Сколько минут прошло с последней подсказки, которую приложение подало тебе в этой сессии само.', 'Cuántos minutos han pasado desde el último aviso que te dio la app por sí sola en esta sesión.', 'Wie viele Minuten seit dem letzten Hinweis vergangen sind, den dir die App in dieser Sitzung von selbst gegeben hat.', 'Combien de minutes se sont écoulées depuis le dernier rappel que l’app t’a envoyé d’elle-même pendant cette séance.', 'Quantos minutos se passaram desde o último aviso que o app te deu por conta própria nesta sessão.')
_tr7('metric.last_cue.more', '数えるのは、アプリが自分から出し、実際に表示された合図だけです — 「テスト」ボタンで試したものは含みません。このセッションでまだ一度も来ていなければ、カードに「—」が表示されます。これは目標でも連続記録でもありません。長い沈黙はうまくいっているという意味ではなく、合図はあなたが何か間違っているという意味でもありません。アプリが最後に声をかけたのがいつか、それだけです。', '只统计应用主动发出、并且确实显示出来的提示——你用“测试”按钮试的不算。本次记录中还没有提示时，卡片显示“—”。这不是目标，也不是连胜：长时间的安静不代表你状态好，出现提示也不代表你做错了什么。它只是应用上一次出声的时间。', 'Считается только подсказка, которую приложение подало само и которая действительно показалась, — твои пробы кнопкой «Тест» не засчитываются. Пока в этой сессии не пришло ни одной, карточка показывает «—». Это не цель и не серия: долгая тишина не значит, что у тебя всё получается, а подсказка не значит, что ты делаешь что-то не так. Это просто момент, когда приложение подало голос в последний раз.', 'Solo cuenta un aviso que la app dio por sí sola y que de verdad se mostró — tus pruebas con el botón «Probar» no cuentan. Mientras no haya llegado ninguno en esta sesión, la tarjeta muestra «—». No es una meta ni una racha: un silencio largo no significa que lo estés haciendo bien, y un aviso no significa que estés haciendo algo mal. Es solo cuándo avisó la app por última vez.', 'Gezählt wird nur ein Hinweis, den die App von selbst gegeben hat und der wirklich angezeigt wurde — deine eigenen Versuche mit dem Knopf „Testen“ zählen nicht. Solange in dieser Sitzung keiner kam, zeigt die Karte „—“. Das ist weder ein Ziel noch eine Serie: Lange Stille heißt nicht, dass es bei dir gut läuft, und ein Hinweis heißt nicht, dass du etwas falsch machst. Es ist nur, wann sich die App zuletzt gemeldet hat.', 'Ne compte qu’un rappel que l’app a envoyé d’elle-même et qui s’est réellement affiché — tes essais avec le bouton « Tester » ne comptent pas. Tant qu’aucun n’est arrivé pendant cette séance, la carte affiche « — ». Ce n’est ni un objectif ni une série : un long silence ne veut pas dire que tu t’en sors bien, et un rappel ne veut pas dire que tu fais quelque chose de travers. C’est juste le moment où l’app s’est manifestée pour la dernière fois.', 'Só conta um aviso que o app deu por conta própria e que apareceu de fato — os seus testes com o botão “Testar” não contam. Enquanto nenhum chegar nesta sessão, o cartão mostra “—”. Não é meta nem sequência: um silêncio longo não quer dizer que você está indo bem, e um aviso não quer dizer que você está fazendo algo errado. É só quando o app avisou pela última vez.')
_tr7('metric.calm_time.title', '平静の時間', '平静时间', 'Время в покое', 'Tiempo en calma', 'Zeit in Ruhe', 'Temps au calme', 'Tempo em calma')
_tr7('metric.calm_time.short', 'セッションのうち、心拍が平静の帯にあった分数。', '本次记录中你的心率在平静区间里待了多少分钟。', 'Сколько минут сессии твой пульс был в зоне покоя.', 'Cuántos minutos de la sesión estuvo tu pulso en la zona de calma.', 'Wie viele Minuten der Sitzung dein Puls in der Ruhezone war.', 'Combien de minutes de la séance ton pouls est resté dans la zone calme.', 'Quantos minutos da sessão o seu pulso passou na zona de calma.')
_tr7('metric.calm_time.more', '平静は「セッションの内訳」パネルと同じ帯です。安静時からの上昇が 10 BPM 未満の心拍のこと。これは心拍の話であって、あなたがどれだけ穏やかに感じたかではありません。スコアではありません — 分数が多いほど良い夜というわけではなく、緊迫した試合で心拍が上がるのは当然のことです。最初の夜、アプリがまだあなたの安静時の値を知らない間は、カードに「—」が表示されます。', '这里的平静和“这次都在哪个区间”面板里是同一个区间：心率比你的平静水平高不到 10 BPM。它说的是心率，而不是你感觉自己有多平静。这不是分数——分钟数多不代表这个晚上更好；紧张的比赛会让心率升高，本来就该如此。第一个晚上，在应用还不了解你的平静水平时，卡片会显示“—”。', 'Покой — та же зона, что и на панели «Где прошла сессия»: пульс меньше чем на 10 BPM выше твоего покоя. Это о пульсе, а не о том, насколько спокойно ты себя чувствовал. Это не очки — больше минут не значит лучший вечер; напряжённый матч поднимает пульс, и так и должно быть. В первый вечер, пока приложение ещё не знает твой покой, карточка показывает «—».', 'La calma es la misma zona que en el panel «Dónde fue la sesión»: pulso a menos de 10 BPM por encima de tu reposo. Habla del pulso, no de lo tranquilo que te sentiste. No es una puntuación — más minutos no significan una noche mejor; una partida tensa sube el pulso, y así debe ser. En tu primera noche, mientras la app aún no conoce tu reposo, la tarjeta muestra «—».', 'Ruhe ist dieselbe Zone wie im Panel „Wo die Sitzung lag“: ein Puls weniger als 10 BPM über deiner Ruhe. Sie sagt etwas über den Puls, nicht darüber, wie ruhig du dich gefühlt hast. Das ist kein Score — mehr Minuten bedeuten keinen besseren Abend; ein angespanntes Match hebt den Puls, und so soll es sein. Am ersten Abend, solange die App deine Ruhe noch nicht kennt, zeigt die Karte „—“.', 'Le calme, c’est la même zone que dans le panneau « Où la séance s’est passée » : un pouls à moins de 10 BPM au-dessus de ton niveau de repos. Ça parle de ton pouls, pas de ton sentiment de calme. Ce n’est pas un score — plus de minutes ne veut pas dire une meilleure soirée ; un match tendu fait monter le pouls, et c’est bien ainsi. Le premier soir, tant que l’app ne connaît pas encore ton niveau de repos, la carte affiche « — ».', 'A calma é a mesma zona do painel “Onde a sessão passou”: pulso menos de 10 BPM acima do seu repouso. Fala do pulso, não de quão calmo você se sentiu. Não é pontuação — mais minutos não significam uma noite melhor; uma partida tensa sobe o pulso, e é assim que deve ser. Na primeira noite, enquanto o app ainda não conhece o seu repouso, o cartão mostra “—”.')
_tr7('metric.signal.title', '信号の品質', '信号质量', 'Качество сигнала', 'Calidad de la señal', 'Signalqualität', 'Qualité du signal', 'Qualidade do sinal')
_tr7('metric.signal.short', 'アプリにどれだけよく届いているか：セッションのうち、実際に心拍が届いていた割合。', '应用能多好地“听到”你：本次记录中有多大比例的时间心率真正传了过来。', 'Насколько хорошо приложение тебя слышит: какую часть сессии к нему действительно приходил пульс.', 'Lo bien que te oye la app: durante qué parte de la sesión le llegó de verdad el pulso.', 'Wie gut dich die App hört: in welchem Anteil der Sitzung dein Puls wirklich ankam.', 'À quel point l’app t’entend bien : pendant quelle part de la séance ton pouls lui est vraiment parvenu.', 'Quão bem o app te ouve: em que parte da sessão o pulso realmente chegou até ele.')
_tr7('metric.signal.more', 'パーセントは、最初のサンプル以降の時間のうち、実際に心拍が届いていた時間の割合です。カードの「·」のあとの数字は、このセッションで心拍が途切れた回数です — 一度も途切れていなければ表示されません。パーセントは1分たってからカードに表示されます。それより早いと、一度の途切れが接続不良のように見えてしまうからです。これは時計 → 電話 → Wi‑Fi → PC という経路の話で、あなたの心臓やあなた自身の話ではありません。低いときは、合図が減ることがあります。数えている途中で心拍が途切れると、アプリは数え直すからです。「履歴」では、時計がつながるまでの待ち時間も含めたセッション全体で計算するため、短いセッションはそこで低めに出ます。', '百分比是从第一个样本起，心率真正传过来的时间所占的比例。卡片上“·”后面的数字是本次记录中心率中断的次数——一次都没有时就不显示。卡片要满一分钟后才显示百分比，太早的话，一个小空档就会看起来像连接很差。它反映的是 手表 → 手机 → Wi‑Fi → 电脑 这条链路，而不是你的心脏，也不是你本人。数值低时，提示可能会变少：如果心率在计时中途中断，应用会从头开始计时。在“历史”里，它按整次记录计算，包括等待手表连接的时间，所以短的记录在那里数值会偏低。', 'Процент — это время, когда пульс действительно приходил, от времени с первого замера. Число после «·» на карточке — сколько раз в этой сессии пульс пропадал; если ни разу, его там нет. Процент появляется на карточке только через минуту — раньше один пропуск выглядел бы как плохое соединение. Это о пути часы → телефон → Wi‑Fi → компьютер, а не о твоём сердце и не о тебе. Когда он низкий, подсказок может быть меньше: если пульс пропадает посреди подсчёта, приложение начинает считать заново. В «Истории» он считается по всей сессии, включая ожидание, пока подключатся часы, поэтому короткие сессии там выходят ниже.', 'El porcentaje es el tiempo en que el pulso llegó de verdad, respecto al tiempo desde la primera muestra. El número tras «·» en la tarjeta es cuántas veces se cortó el pulso en esta sesión — si no se cortó ninguna, no aparece. El porcentaje aparece en la tarjeta solo pasado un minuto; antes, un solo hueco parecería una mala conexión. Habla del camino reloj → móvil → Wi‑Fi → PC, no de tu corazón ni de ti. Cuando es bajo, puede haber menos avisos: si el pulso se corta a mitad del conteo, la app empieza a contar de nuevo. En el Historial se calcula sobre toda la sesión, incluida la espera hasta que se conectó el reloj, por eso ahí las sesiones cortas salen más bajas.', 'Der Prozentwert ist die Zeit, in der der Puls wirklich ankam, bezogen auf die Zeit seit dem ersten Messwert. Die Zahl hinter „·“ auf der Karte gibt an, wie oft der Puls in dieser Sitzung ausgefallen ist — wenn nie, steht sie nicht da. Der Prozentwert erscheint auf der Karte erst nach einer Minute; früher würde eine einzige Lücke wie eine schlechte Verbindung aussehen. Er sagt etwas über den Weg Uhr → Handy → WLAN → PC, nicht über dein Herz oder über dich. Ist er niedrig, kann es weniger Hinweise geben: Wenn der Puls mitten im Zählen ausfällt, beginnt die App von vorn zu zählen. Im Verlauf wird er über die ganze Sitzung berechnet, einschließlich des Wartens, bis sich die Uhr verbunden hat, deshalb fallen kurze Sitzungen dort niedriger aus.', 'Le pourcentage est le temps où le pouls est vraiment arrivé, rapporté au temps écoulé depuis le premier échantillon. Le chiffre après « · » sur la carte indique combien de fois le pouls a décroché pendant cette séance — s’il n’a jamais décroché, il n’apparaît pas. La carte n’affiche le pourcentage qu’au bout d’une minute ; plus tôt, un seul trou ressemblerait à une mauvaise connexion. Ça parle du trajet montre → téléphone → Wi‑Fi → ordinateur, pas de ton cœur ni de toi. Quand il est bas, il peut y avoir moins de rappels : si le pouls décroche au milieu du comptage, l’app recommence à compter. Dans l’Historique, il est calculé sur toute la séance, y compris l’attente de la connexion de la montre ; c’est pourquoi les séances courtes y sortent plus bas.', 'A porcentagem é o tempo em que o pulso realmente chegou, em relação ao tempo desde a primeira amostra. O número depois do “·” no cartão é quantas vezes o sinal do pulso caiu nesta sessão — se não caiu nenhuma vez, ele não aparece. A porcentagem só aparece no cartão depois de um minuto; antes disso, uma única falha pareceria uma conexão ruim. Fala do caminho relógio → celular → Wi‑Fi → PC, não do seu coração nem de você. Quando está baixa, pode haver menos avisos: se o sinal do pulso cai no meio da contagem, o app começa a contar de novo. No Histórico, é calculada sobre a sessão inteira, incluindo a espera até o relógio se conectar, por isso lá as sessões curtas saem mais baixas.')
_tr7('metric.felt_vs_measured.title', '感覚と計測', '感受与测量', 'Ощущаемое и измеренное', 'Sentido y medido', 'Gefühlt und gemessen', 'Ressenti et mesuré', 'Sentido e medido')
_tr7('metric.felt_vs_measured.short', 'アンケートで答えた「感じた負荷」と、計測した負荷のピークを並べたもの。どちらも 0–10。', '你在问卷里填写的主观强度，与测得的负荷峰值并排显示，两者都是 0–10。', 'Твоя ощущаемая нагрузка из опроса рядом с измеренным пиком нагрузки, оба числа 0–10.', 'Tu carga percibida en el cuestionario junto al pico de carga medido, ambos de 0–10.', 'Deine empfundene Last aus dem Fragebogen neben der gemessenen Last-Spitze, beide 0–10.', 'Ta charge ressentie, d’après le questionnaire, à côté du pic de charge mesuré, les deux sur 0–10.', 'A sua carga percebida no questionário ao lado do pico de carga medido, ambos de 0–10.')
_tr7('metric.felt_vs_measured.more', '「今日」のカードは、このワールド（ゲームまたは仕事）で最後に終わったセッションを、「履歴」の詳細は選んだセッションを使います。1つ目の数字は、セッション後のアンケートであなたが評価した負荷です。2つ目は、同じセッションの最高負荷（0–100 のピーク）を10で割ったものです。一致しなくてもかまいませんし、どちらも「正解」ではありません — 心拍はあなたがどう感じたかを見られず、あなたは一拍一拍を感じられません。両者の差は誤りではなく、情報です。アンケートを飛ばした場合は「—」が表示されます。', '“今天”页面上的卡片取这个世界（游戏或工作）最近一次已结束的记录，“历史”里的详情则取你选中的那一次。第一个数字是你在记录结束后的问卷里给负荷打的分。第二个是同一次记录的最高负荷（0–100 的峰值）除以十。两者不一定一致，也没有哪个才是“正确的”——心率看不到你当时的感受，你也感觉不到每一次心跳。两者之间的差距不是错误，而是信息。如果你跳过了问卷，就显示“—”。', 'Карточка на «Сегодня» берёт последнюю завершённую сессию этого мира (Игра или Работа), подробности в «Истории» — ту, которую ты выбрал. Первое число — как ты оценил нагрузку в опросе после сессии. Второе — самая высокая нагрузка той же сессии (пик 0–100), делённая на десять. Они не обязаны совпадать, и ни одно из них не «правильное» — пульс не видит, как тебе было, а ты не чувствуешь каждый удар. Разница между ними — не ошибка, а информация. Если ты пропустил опрос, будет «—».', 'La tarjeta de Hoy toma la última sesión terminada de este mundo (Juego o Trabajo); el detalle en el Historial, la que elegiste. El primer número es cómo valoraste la carga en el cuestionario tras la sesión. El segundo es la carga más alta de esa misma sesión (el pico de 0–100) dividida entre diez. No tienen por qué coincidir y ninguno es «el correcto» — el pulso no ve cómo te sentías, y tú no sientes cada latido. La diferencia entre ellos no es un error, es información. Si te saltaste el cuestionario, muestra «—».', 'Die Karte auf Heute nimmt die letzte beendete Sitzung dieser Welt (Spiel oder Arbeit), das Detail im Verlauf die, die du ausgewählt hast. Die erste Zahl ist, wie du die Last im Fragebogen nach der Sitzung bewertet hast. Die zweite ist die höchste Last derselben Sitzung (Spitze 0–100) geteilt durch zehn. Sie müssen nicht übereinstimmen, und keine ist „die richtige“ — der Puls sieht nicht, wie es dir ging, und du spürst nicht jeden Schlag. Der Unterschied zwischen ihnen ist kein Fehler, sondern eine Information. Wenn du den Fragebogen übersprungen hast, zeigt sie „—“.', 'La carte de la page Aujourd’hui prend la dernière séance terminée de ce monde (Jeu ou Travail), le détail dans l’Historique prend celle que tu as choisie. Le premier chiffre est la note que tu as donnée à la charge dans le questionnaire après la séance. Le second est la charge la plus haute de cette même séance (pic 0–100) divisée par dix. Ils ne doivent pas forcément correspondre, et aucun n’est « le bon » — le pouls ne voit pas comment tu te sentais, et tu ne sens pas chaque battement. L’écart entre eux n’est pas une erreur, c’est une information. Si tu as sauté le questionnaire, la carte affiche « — ».', 'O cartão em Hoje usa a última sessão encerrada deste mundo (Jogo ou Trabalho); o detalhe no Histórico usa a que você escolheu. O primeiro número é como você avaliou a carga no questionário depois da sessão. O segundo é a carga mais alta dessa mesma sessão (o pico de 0–100) dividida por dez. Eles não precisam bater, e nenhum dos dois é “o certo” — o pulso não vê como você se sentiu, e você não sente cada batida. A diferença entre eles não é um erro, é informação. Se você pulou o questionário, aparece “—”.')
_tr7('dashboard.unit.session_len', 'セッション開始から', '自本次记录开始', 'с начала сессии', 'desde el inicio de la sesión', 'seit Sitzungsbeginn', 'depuis le début de la séance', 'desde o início da sessão')
_tr7('dashboard.unit.last_cue', '最後の合図から', '距上次提示', 'с последней подсказки', 'desde el último aviso', 'seit dem letzten Hinweis', 'depuis le dernier rappel', 'desde o último aviso')
_tr7('dashboard.unit.calm_time', 'このセッションの平静', '本次处于平静', 'в покое за сессию', 'en calma esta sesión', 'in Ruhe in dieser Sitzung', 'au calme pendant la séance', 'em calma nesta sessão')
_tr7('dashboard.unit.signal', '心拍が届いた時間', '有心率的时间', 'времени с пульсом', 'del tiempo con pulso', 'der Zeit mit Puls', 'du temps avec pouls', 'do tempo com pulso')
_tr7('dashboard.unit.felt_vs_measured', '感覚 · 計測、0–10', '感受 · 测量，0–10', 'ощущаемое · измеренное, 0–10', 'sentido · medido, 0–10', 'gefühlt · gemessen, 0–10', 'ressenti · mesuré, 0–10', 'sentido · medido, 0–10')
_tr7('dashboard.fmt.min', '{n} 分', '{n} 分钟', '{n} мин', '{n} min', '{n} min', '{n} min', '{n} min')
_tr7('dashboard.fmt.h_min', '{h} 時間 {m} 分', '{h} 小时 {m} 分', '{h} ч {m} мин', '{h} h {m} min', '{h} h {m} min', '{h} h {m} min', '{h} h {m} min')
_tr7('dashboard.fmt.pct', '{n}%', '{n}%', '{n} %', '{n} %', '{n} %', '{n} %', '{n}%')
_tr7('insight.cue_dropouts', 'ここ数晩、数えている最中に心拍が一晩あたり平均 {n} 回途切れ、そのたびに数え直しになりました — そのため合図が少なくなることがあります。心拍は時計から電話へ Bluetooth で、電話から PC へ Wi‑Fi で届きます — 時計は電話のそばに、電話は Wi‑Fi ルーターの近くに置いてください。PC から離れるときは、電話を持っていってください。', '最近几个晚上，你的心率平均每晚有 {n} 次恰好在计时过程中中断，每次计时都得从头开始——所以提示可能会变少。心率从手表通过蓝牙传到手机，再从手机通过 Wi‑Fi 传到电脑——让手表靠近手机，手机靠近 Wi‑Fi 路由器。离开电脑时，把手机带在身边。', 'За последние вечера пульс у тебя пропадал в среднем {n}× за вечер как раз во время подсчёта, и подсчёт каждый раз начинался заново — поэтому подсказок может быть меньше. Пульс идёт с часов на телефон по Bluetooth, а с телефона по Wi‑Fi на компьютер — держи часы рядом с телефоном, а телефон поближе к Wi‑Fi роутеру. Когда отходишь от компьютера, бери телефон с собой.', 'En las últimas noches, el pulso se te cortó de media {n}× por noche justo durante el conteo, y cada vez el conteo empezó de nuevo — por eso puede haber menos avisos. El pulso va del reloj al móvil por Bluetooth y del móvil al PC por Wi‑Fi — ten el reloj cerca del móvil y el móvil cerca del router Wi‑Fi. Cuando te alejes del PC, llévate el móvil.', 'Dein Puls ist an den letzten Abenden im Schnitt {n}× pro Abend genau während des Zählens ausgefallen, und das Zählen begann jedes Mal von vorn — deshalb kann es weniger Hinweise geben. Der Puls geht von der Uhr per Bluetooth zum Handy und vom Handy über WLAN zum PC — halte die Uhr beim Handy und das Handy nah am WLAN-Router. Wenn du vom PC weggehst, nimm das Handy mit.', 'Ces derniers soirs, ton pouls a décroché en moyenne {n}× par soirée pile pendant le comptage, et le comptage a chaque fois recommencé à zéro — c’est pourquoi il peut y avoir moins de rappels. Le pouls passe de la montre au téléphone par Bluetooth, et du téléphone à l’ordinateur par Wi‑Fi — garde la montre près du téléphone et le téléphone près du routeur Wi‑Fi. Quand tu t’éloignes de l’ordinateur, emporte le téléphone avec toi.', 'Nas últimas noites, o sinal do pulso caiu em média {n}× por noite justamente durante a contagem, e a contagem recomeçou do zero toda vez — por isso pode haver menos avisos. O pulso vai do relógio para o celular por Bluetooth, e do celular para o PC por Wi‑Fi — mantenha o relógio perto do celular e o celular perto do roteador Wi‑Fi. Quando sair de perto do PC, leve o celular junto.')
_tr7('insight.cue_never_above', 'ここ {n} 晩、負荷は一度もしきい値を超えませんでした — だから、アプリには声をかける理由がありませんでした。しきい値は設定ではありません — アプリがあなたのセッションから算出し、あなたを知るにつれて動かしていきます。現在の値は「設定」→「トリガー」で確認できます。', '最近 {n} 个晚上，负荷一次都没有超过阈值——所以应用没有理由出声。阈值不是一项设置——应用根据你的记录计算它，并随着对你的了解逐步调整。当前的阈值可以在“设置 → 触发器”里看到。', 'За последние вечера ({n}) нагрузка ни разу не поднималась выше порога — так что приложению не было повода подать голос. Порог — не настройка: приложение вычисляет его по твоим сессиям и сдвигает, по мере того как узнаёт тебя. Текущий видно в Настройках → Триггеры.', 'En las últimas {n} noches la carga no superó el umbral ni una vez — así que la app no tenía por qué avisar. El umbral no es un ajuste — la app lo calcula a partir de tus sesiones y lo va moviendo a medida que te conoce. El actual lo ves en Ajustes → Disparadores.', 'An den letzten {n} Abenden ist die Last kein einziges Mal über die Schwelle gekommen — die App hatte also keinen Grund, sich zu melden. Die Schwelle ist keine Einstellung — die App berechnet sie aus deinen Sitzungen und verschiebt sie, während sie dich kennenlernt. Die aktuelle siehst du unter Einstellungen → Trigger.', 'Ces {n} derniers soirs, la charge n’a pas une seule fois dépassé le seuil — l’app n’avait donc aucune raison de se manifester. Le seuil n’est pas un réglage — l’app le calcule à partir de tes séances et le déplace à mesure qu’elle te connaît. Tu vois le seuil actuel dans Paramètres → Déclencheurs.', 'Nas últimas {n} noites, a carga não passou do limiar nem uma vez — então o app não tinha motivo para avisar. O limiar não é uma configuração — o app o calcula a partir das suas sessões e o ajusta conforme vai te conhecendo. O atual você vê em Configurações → Gatilhos.')
_tr7('insight.cue_almost', '負荷は上がりましたが、連続で最長 {sec} 秒 — {need} 秒には届きませんでした。惜しいところでした。アプリは、短いピークのたびに声をかけないよう、負荷が高いまま続くのをわざと待っています。', '负荷确实升高过，但最长只连续了 {sec} 秒——离 {need} 秒还差一点。差得不多。应用会刻意等负荷在高位保持住，以免每个短暂的峰值都出声。', 'Нагрузка поднималась, но дольше всего {sec} с подряд — до {need} с не хватило. Было близко. Приложение намеренно ждёт, пока нагрузка продержится наверху, чтобы не подавать голос при каждом коротком пике.', 'La carga sí subió, pero lo más largo fueron {sec} s seguidos — faltaba llegar a {need} s. Estuvo cerca. La app espera a propósito a que la carga se mantenga alta, para no avisar con cada pico breve.', 'Die Last war oben, aber höchstens {sec} s am Stück — bis {need} s hat es nicht gereicht. Es war knapp. Die App wartet absichtlich, bis die Last oben bleibt, damit sie sich nicht bei jeder kurzen Spitze meldet.', 'La charge est bien montée, mais au plus long {sec} s d’affilée — il en fallait {need}. C’était juste. L’app attend exprès que la charge tienne, pour ne pas se manifester à chaque pic bref.', 'A carga ficou alta, mas por no máximo {sec} s seguidos — não deu para chegar a {need} s. Foi por pouco. O app espera de propósito que a carga se mantenha alta, para não avisar a cada pico curto.')
_tr7('insight.cue_far', '負荷はしきい値を超えましたが、ほんの短いあいだでした — 連続で最長 {sec} 秒、必要なのは {need} 秒です。あなたの体は、アプリが待つよりも速く上がり下がりします。短いピークでは、アプリはわざと声をかけません — ここで設定することは何もありません。', '负荷确实超过了阈值，但只是一会儿——最长 {sec} 秒，而需要的是 {need} 秒。你的身体起落比应用等待的时间更快。应用刻意不对短暂的峰值出声——这里没有什么需要设置的。', 'Нагрузка поднималась выше порога, но лишь ненадолго — дольше всего {sec} с из нужных {need} с. Твоё тело поднимается и опускается быстрее, чем ждёт приложение. На короткие пики приложение намеренно не подаёт голос — настраивать здесь нечего.', 'La carga superó el umbral, pero solo un momento — lo más largo fueron {sec} s de los {need} s necesarios. Tu cuerpo sube y baja más rápido de lo que la app espera. Con los picos breves la app no avisa a propósito — aquí no hay nada que ajustar.', 'Die Last kam über die Schwelle, aber nur kurz — höchstens {sec} s von den nötigen {need} s. Dein Körper geht schneller hoch und runter, als die App wartet. Bei kurzen Spitzen meldet sich die App absichtlich nicht — hier gibt es nichts einzustellen.', 'La charge a dépassé le seuil, mais seulement un instant — au plus long {sec} s sur les {need} s nécessaires. Ton corps monte et redescend plus vite que ce que l’app attend. C’est exprès que l’app ne se manifeste pas sur les pics brefs — il n’y a rien à régler ici.', 'A carga passou do limiar, mas só por um instante — no máximo {sec} s dos {need} s necessários. O seu corpo sobe e desce mais rápido do que o app espera. Em picos curtos o app não avisa, de propósito — não há nada para ajustar aqui.')
_tr7('insight.resting_up', '最近のセッションでは、安静時ベースラインが以前より {delta} BPM 高くなっています — 睡眠不足、カフェイン、それとも風邪？ 必ずしもゲームのせいではありません。', '最近几次记录的静息基线比之前高 {delta} BPM——也许是睡得少、咖啡因或者感冒了？不一定是游戏造成的。', 'Базовая линия покоя в последних сессиях на {delta} BPM выше, чем в предыдущих, — может, меньше сна, кофеин или простуда? Не обязательно из-за игр.', 'Tu línea base en reposo está {delta} BPM más alta en las últimas sesiones que en las anteriores — ¿quizá menos sueño, cafeína o un resfriado? No viene necesariamente del juego.', 'Deine Ruhebasislinie liegt in den letzten Sitzungen {delta} BPM höher als in den Sitzungen davor — vielleicht weniger Schlaf, Koffein oder eine Erkältung? Das kommt nicht unbedingt vom Spielen.', 'Sur les dernières séances, ta ligne de base au repos est plus haute de {delta} BPM que sur les précédentes — peut-être moins de sommeil, de la caféine ou un rhume ? Ce n’est pas forcément dû au jeu.', 'A sua linha de base em repouso está {delta} BPM mais alta nas últimas sessões do que nas anteriores — talvez menos sono, cafeína ou um resfriado? Não é necessariamente por causa do jogo.')
_tr7('insight.resting_down', '最近のセッションでは、安静時ベースラインが以前より {delta} BPM 低くなっています。睡眠がよくなった、カフェインが減った、あるいは単に計測中に穏やかな時間が多かっただけかもしれません — 数字ひとつでは見分けられません。', '最近几次记录的静息基线比之前低 {delta} BPM。可能是睡得更好、咖啡因更少，也可能只是测量时恰好比较平静——单凭一个数字分辨不出来。', 'Базовая линия покоя в последних сессиях на {delta} BPM ниже, чем в предыдущих. Это может быть лучший сон, меньше кофеина или просто более спокойные моменты во время измерения — одно число этого не различит.', 'Tu línea base en reposo está {delta} BPM más baja en las últimas sesiones que en las anteriores. Puede ser mejor sueño, menos cafeína o solo momentos más tranquilos al medir — un solo número no lo distingue.', 'Deine Ruhebasislinie liegt in den letzten Sitzungen {delta} BPM niedriger als in den Sitzungen davor. Das kann besserer Schlaf sein, weniger Koffein oder einfach ruhigere Momente beim Messen — eine einzelne Zahl kann das nicht unterscheiden.', 'Sur les dernières séances, ta ligne de base au repos est plus basse de {delta} BPM que sur les précédentes. Ça peut être un meilleur sommeil, moins de caféine ou simplement des moments plus calmes pendant la mesure — un seul chiffre ne permet pas de trancher.', 'A sua linha de base em repouso está {delta} BPM mais baixa nas últimas sessões do que nas anteriores. Pode ser sono melhor, menos cafeína ou só momentos mais calmos durante a medição — um único número não consegue distinguir.')
_tr7('insight.hrr_up', '最近のセッションでは、心拍回復が以前より {delta} BPM 速くなっています。いい兆しです — ただ、数回のセッションからでは確かなことは言えず、あくまで手がかりです。', '最近几次记录的心率恢复比之前快 {delta} BPM。是个不错的信号——但只凭几次记录，这更像是一个迹象，而不是定论。', 'Восстановление пульса в последних сессиях на {delta} BPM быстрее, чем раньше. Хороший сигнал — но по нескольким сессиям это скорее намёк, чем уверенность.', 'La recuperación del pulso es {delta} BPM más rápida en las últimas sesiones que antes. Buena señal — pero con pocas sesiones es más un indicio que una certeza.', 'Die Herzfrequenz-Erholung ist in den letzten Sitzungen {delta} BPM schneller als vorher. Ein schönes Signal — aber aus ein paar Sitzungen ist das eher ein Anzeichen als eine Gewissheit.', 'Sur les dernières séances, ta récupération cardiaque est plus rapide de {delta} BPM qu’avant. Joli signe — mais sur quelques séances, c’est plutôt un indice qu’une certitude.', 'A recuperação do pulso está {delta} BPM mais rápida nas últimas sessões do que antes. Um bom sinal — mas, com poucas sessões, é mais um indício do que uma certeza.')
_tr7('insight.hrr_down', '最近のセッションでは、心拍回復が以前より {delta} BPM 遅くなっています。数回のセッションからでは、あくまで手がかりです — 心拍がどれだけ高く跳ねたかにもよりますし、睡眠、疲れ、あるいはゲームの種類の違いが関係しているかもしれません。', '最近几次记录的心率恢复比之前慢 {delta} BPM。只凭几次记录，这更像是一个迹象——它也取决于心率冲得有多高，背后可能是睡眠、疲劳或者玩的游戏类型不同。', 'Восстановление пульса в последних сессиях на {delta} BPM медленнее, чем раньше. По нескольким сессиям это скорее намёк — зависит и от того, насколько высоко подскочил пульс, а за этим могут стоять сон, усталость или другой тип игр.', 'La recuperación del pulso es {delta} BPM más lenta en las últimas sesiones que antes. Con pocas sesiones es más un indicio que una certeza — también depende de lo alto que se disparó el pulso, y puede deberse al sueño, al cansancio o a otro tipo de juegos.', 'Die Herzfrequenz-Erholung ist in den letzten Sitzungen {delta} BPM langsamer als vorher. Aus ein paar Sitzungen ist das eher ein Anzeichen — es hängt auch davon ab, wie hoch der Puls gesprungen ist, und dahinter können Schlaf, Müdigkeit oder eine andere Art von Spielen stecken.', 'Sur les dernières séances, ta récupération cardiaque est plus lente de {delta} BPM qu’avant. Sur quelques séances, c’est plutôt un indice — ça dépend aussi de la hauteur à laquelle ton pouls est monté, et le sommeil, la fatigue ou un autre type de jeu peuvent y être pour quelque chose.', 'A recuperação do pulso está {delta} BPM mais lenta nas últimas sessões do que antes. Com poucas sessões, é mais um indício — depende também de quão alto o pulso subiu, e pode ter a ver com sono, cansaço ou outro tipo de jogo.')
_tr7('insight.triggers_early', '1.5 時間以上のセッションでは、合図の {share}% が最初の1時間に来ました。これが続くなら、セッションの始まりそのものがあなたを高ぶらせているのかもしれません — もっと穏やかな始め方を試して、変わるかどうか見てみてください。', '在 1.5 小时及以上的记录中，{share}% 的提示出现在第一个小时。如果反复如此，也许正是开局让你紧绷起来——试试更平缓的热身，看看情况是否改变。', 'В сессиях от 1,5 ч {share} % подсказок пришлись на первый час. Если это повторяется, возможно, тебя разгоняет именно начало — попробуй более спокойный разгон и посмотри, изменится ли что-то.', 'En las sesiones de 1,5 h o más, el {share} % de los avisos llegó en la primera hora. Si se repite, quizá lo que te acelera sea justo el comienzo — prueba un arranque más tranquilo y observa si cambia.', 'In Sitzungen ab 1,5 h kamen {share} % der Hinweise in der ersten Stunde. Wenn sich das wiederholt, bringt dich vielleicht gerade der Anfang auf Touren — probier einen ruhigeren Einstieg und beobachte, ob sich das ändert.', 'Dans les séances de 1,5 h et plus, {share} % des rappels sont arrivés dans la première heure. Si ça se répète, c’est peut-être justement le début qui te fait monter en régime — essaie un démarrage plus tranquille et regarde si ça change.', 'Nas sessões de 1,5 h ou mais, {share}% dos avisos vieram na primeira hora. Se isso se repetir, talvez seja justamente o começo que te acelera — tente um início mais tranquilo e veja se muda.')
_tr7('insight.triggers_late', '2.5 時間以上のセッションでは、合図の {share}% が2時間を過ぎてから来ました — 長いセッションは緊張を長引かせるのかもしれません。休憩を挟んだ短めのセッションを試してみてください。', '在 2.5 小时及以上的记录中，{share}% 的提示在两小时之后才出现——长时间连续玩可能让你一直处于紧绷状态；试试玩得短一些，中间休息一下。', 'В сессиях от 2,5 ч {share} % подсказок пришли только после двух часов — долгие сессии могут держать тебя в напряжении; попробуй сессии покороче с перерывом.', 'En las sesiones de 2,5 h o más, el {share} % de los avisos llegó después de dos horas — las sesiones largas pueden mantenerte en tensión; prueba sesiones más cortas con una pausa.', 'In Sitzungen ab 2,5 h kamen {share} % der Hinweise erst nach zwei Stunden — lange Sitzungen können dich unter Spannung halten; probier kürzere Sitzungen mit einer Pause.', 'Dans les séances de 2,5 h et plus, {share} % des rappels sont arrivés après deux heures — les longues séances peuvent te maintenir sous tension ; essaie des séances plus courtes avec une pause.', 'Nas sessões de 2,5 h ou mais, {share}% dos avisos vieram só depois de duas horas — sessões longas podem te manter em tensão; tente sessões mais curtas, com pausa.')
_tr7('insight.over_up', '最近のセッションでは、以前よりもセッションの大きな割合をしきい値超えで過ごしています（平均 {minutes} 分）。ゲームのせいかもしれませんし、睡眠やカフェインのせいかもしれません — あるいは単に、アプリがセッションのたびにあなたのデータからしきい値を微調整しているだけかもしれません。この状態が続くなら、「ガイド」の呼吸法を試してみるのもいいでしょう。', '最近几次记录中，你在阈值以上的时间占比比之前更大（平均 {minutes} 分钟）。可能是游戏的原因，也可能是睡眠或咖啡因——或者只是因为应用在每次记录后都会根据你的数据微调阈值。如果一直这样，可以试试“指南”里的呼吸方法。', 'В последних сессиях ты провёл выше порога большую часть сессии, чем раньше (в среднем {minutes} мин). Причиной может быть игра, но и сон или кофеин — или просто то, что приложение после каждой сессии уточняет порог по твоим данным. Если так и останется, можешь попробовать дыхание из «Справочника».', 'En las últimas sesiones pasaste por encima del límite una parte mayor de la sesión que antes (media {minutes} min). Puede deberse al juego, pero también al sueño o a la cafeína — o simplemente a que la app afina el límite tras cada sesión según tus datos. Si sigue así, puedes probar la respiración de la Guía.', 'In den letzten Sitzungen hast du einen größeren Teil der Sitzung über der Grenze verbracht als vorher (Schnitt {minutes} Min). Dahinter kann das Spiel stecken, aber auch Schlaf oder Koffein — oder einfach, dass die App die Grenze nach jeder Sitzung anhand deiner Daten nachjustiert. Wenn es so bleibt, kannst du die Atmung aus dem Leitfaden ausprobieren.', 'Sur les dernières séances, tu as passé au-dessus du seuil une plus grande part de la séance qu’avant (moyenne {minutes} min). Ça peut venir du jeu, mais aussi du sommeil ou de la caféine — ou simplement du fait que l’app affine le seuil après chaque séance d’après tes données. Si ça reste ainsi, tu peux essayer la respiration du Guide.', 'Nas últimas sessões, você passou uma parte maior da sessão acima do limite do que antes (média de {minutes} min). Pode ser o jogo, mas também o sono ou a cafeína — ou só o fato de o app ajustar o limite depois de cada sessão com base nos seus dados. Se continuar assim, você pode experimentar a respiração do Guia.')
_tr7('insight.steady', '{n} 回のセッションで、アプリはまだ何も気づいていません。', '在 {n} 次记录中，应用暂时没有发现什么。', 'Приложение пока ничего не заметило (сессий: {n}).', 'En {n} sesiones la app todavía no ha notado nada.', 'In {n} Sitzungen ist der App bisher nichts aufgefallen.', 'Sur {n} séances, l’app n’a encore rien remarqué.', 'Em {n} sessões, o app ainda não notou nada.')
_tr7('guide.philosophy.source12', '息を吐くと心拍は自然に遅くなる（Lehrer & Gevirtz, 2014）', '呼气时心率会自然放慢（Lehrer & Gevirtz，2014）', 'на выдохе пульс естественным образом замедляется (Lehrer & Gevirtz, 2014)', 'al exhalar, el pulso se ralentiza de forma natural (Lehrer & Gevirtz, 2014)', 'beim Ausatmen wird der Puls von Natur aus langsamer (Lehrer & Gevirtz, 2014)', 'à l’expiration, le pouls ralentit naturellement (Lehrer & Gevirtz, 2014)', 'ao expirar, o coração desacelera naturalmente (Lehrer & Gevirtz, 2014)')
_tr7('guide.philosophy.source11', 'ゆっくりした呼吸は、より穏やかな状態と結びついている（Zaccaro ら, 2018）', '缓慢呼吸与更平静的状态相关（Zaccaro 等，2018）', 'медленное дыхание связано с более спокойным состоянием (Zaccaro и др., 2018)', 'la respiración lenta se asocia con un estado más tranquilo (Zaccaro et al., 2018)', 'langsames Atmen geht mit einem ruhigeren Zustand einher (Zaccaro u. a., 2018)', 'une respiration lente va de pair avec un état plus calme (Zaccaro et al., 2018)', 'a respiração lenta está associada a um estado mais calmo (Zaccaro et al., 2018)')
_tr7('guide.philosophy.source10', '競技的なプレイは、心臓に本物のストレス反応を引き起こす（Ketelhut & Nigg, 2024）', '竞技游戏会引发心脏真实的应激反应（Ketelhut & Nigg，2024）', 'соревновательная игра запускает настоящую стрессовую реакцию сердца (Ketelhut & Nigg, 2024)', 'el juego competitivo desencadena una respuesta de estrés real en el corazón (Ketelhut & Nigg, 2024)', 'kompetitives Spielen löst eine echte Stressreaktion des Herzens aus (Ketelhut & Nigg, 2024)', 'le jeu compétitif déclenche une véritable réaction de stress du cœur (Ketelhut & Nigg, 2024)', 'o jogo competitivo desencadeia uma resposta real de estresse no coração (Ketelhut & Nigg, 2024)')
_tr7('ob.step3.body2', 'もうひとつ。アプリはセッションをすべて記録します。数週間プレイすると、あなた自身の傾向を見せ始めます — たとえば、緊張した場面のあとどれだけ速く平静に戻るか — 感覚ではなく、はっきりした数字で。', '还有一点：应用会记住每一次记录。玩上几周之后，它会开始向你展示你自己的趋势——比如紧张过后你多快平复下来——白纸黑字，而不是凭感觉。', 'И ещё: приложение помнит каждую сессию. Через пару недель игры оно начнёт показывать твои собственные тренды — например, как быстро ты приходишь в норму после напряжения, — чёрным по белому, а не по ощущениям.', 'Y una cosa más: la app recuerda cada sesión. Tras unas semanas de juego empieza a mostrarte tus propias tendencias — por ejemplo, lo rápido que vuelves a la calma después de un momento de tensión — negro sobre blanco, no a ojo.', 'Und noch etwas: Die App merkt sich jede Sitzung. Nach ein paar Wochen Spielen zeigt sie dir deine eigenen Trends — zum Beispiel, wie schnell du nach einer Anspannung wieder runterkommst — schwarz auf weiß, nicht nach Gefühl.', 'Et encore : l’app garde en mémoire chaque séance. Après quelques semaines de jeu, elle commence à te montrer tes propres tendances — par exemple à quelle vitesse tu retrouves ton calme après un moment intense — noir sur blanc, pas au feeling.', 'E mais uma coisa: o app se lembra de cada sessão. Depois de algumas semanas jogando, ele começa a te mostrar as suas próprias tendências — por exemplo, com que rapidez você volta à calma depois de um momento tenso — preto no branco, não por impressão.')
_tr7('history.minutes', '{m} 分', '{m} 分钟', '{m} мин', '{m} min', '{m} min', '{m} min', '{m} min')
_tr7('dock.snooze_active_tip', '今はいい — {until} まで声をかけません', '现在不要 — {until} 之前我不会出声', 'Не сейчас — до {until} не подам голос', 'Ahora no — hasta las {until} no aviso', 'Jetzt nicht — bis {until} melde ich mich nicht', 'Pas maintenant — je ne me manifeste pas avant {until}', 'Agora não — até {until} não vou avisar')
_tr7('dnes.empty_body', '時計をつなぐと、アプリはここに心拍と負荷を描きます — そして負荷がしばらく高いまま続くと、自分から合図を出します。', '配对手表后，应用会在这里画出你的心率和负荷——当你的负荷持续偏高一阵子时，它会主动给你一条提示。', 'Когда подключишь часы, приложение будет рисовать здесь пульс и нагрузку — а когда нагрузка какое-то время держится высокой, само даст подсказку.', 'Cuando vincules el reloj, la app dibujará aquí tu pulso y tu carga — y cuando la carga se mantenga alta un rato, te avisará por sí sola.', 'Sobald du die Uhr verbindest, zeichnet dir die App hier Puls und Last — und wenn deine Last eine Weile oben bleibt, meldet sie sich von selbst mit einem Hinweis.', 'Quand tu connectes ta montre, l’app dessine ici ton pouls et ta charge — et quand ta charge reste haute un moment, elle se manifeste d’elle-même avec un rappel.', 'Quando você parear o relógio, o app desenha aqui o seu pulso e a sua carga — e, quando a carga fica alta por um tempo, ele avisa por conta própria.')
_tr7('settings.auto_profile_sub', '知っているゲーム：{games}。数秒ごとに、実行中のプロセス名をこのリストと照らし合わせます – プロセスからそれ以外は何も読みません。ゲームを見つけたら、そのプロファイルに切り替え（なければ既定の合図で作成します）、監視を始めます。ゲームを閉じると、私が始めた監視なら止めます。オフ = プロセスのリストをまったく読みません。', '我认识的游戏：{games}。每隔几秒，我会把正在运行的进程名称和这个列表对比——除此之外不从进程读取任何东西。找到游戏后，我会切换到它的配置文件（如果你还没有，我会用默认提示新建一个）并开始监听。你关闭游戏时，如果监听是我启动的，我会把它停止。关闭 = 我完全不读取进程列表。', 'Игры, которые я знаю: {games}. Каждые несколько секунд я сравниваю названия запущенных процессов с этим списком – больше ничего из процессов не читаю. Когда нахожу игру, переключаюсь на её профиль (если его нет, создаю его с подсказками по умолчанию) и начинаю слушать. Когда ты закрываешь игру, я перестаю слушать, если это я начала слушать. Выключено = список процессов я вообще не читаю.', 'Juegos que conozco: {games}. Cada pocos segundos comparo los nombres de los procesos en ejecución con esta lista – de los procesos no leo nada más. Cuando encuentro un juego, cambio a su perfil (si no lo tienes, lo creo con los avisos predeterminados) y empiezo a escuchar. Cuando cierras el juego, dejo de escuchar, si lo inicié yo misma. Apagado = no leo la lista de procesos en absoluto.', 'Spiele, die ich kenne: {games}. Alle paar Sekunden vergleiche ich die Namen der laufenden Prozesse mit dieser Liste – sonst lese ich nichts aus den Prozessen. Wenn ich ein Spiel finde, wechsle ich zu seinem Profil (hast du keins, lege ich eins mit den Standard-Hinweisen an) und starte das Zuhören. Wenn du das Spiel schließt, stoppe ich das Zuhören wieder, falls ich es gestartet habe. Aus = die Prozessliste lese ich gar nicht.', 'Jeux que je connais : {games}. Toutes les quelques secondes, je compare les noms des processus en cours avec cette liste – je ne lis rien d’autre des processus. Quand je trouve un jeu, je passe sur son profil (si tu n’en as pas, je le crée avec les rappels par défaut) et je lance l’écoute. Quand tu fermes le jeu, j’arrête l’écoute, si c’est moi qui l’ai lancée. Désactivé = je ne lis pas du tout la liste des processus.', 'Jogos que eu conheço: {games}. A cada poucos segundos, comparo os nomes dos processos em execução com esta lista – não leio mais nada dos processos. Quando encontro um jogo, troco para o perfil dele (se você não tiver um, crio com os avisos padrão) e começo a ouvir. Quando você fecha o jogo, paro de ouvir, se fui eu que comecei. Desativado = não leio a lista de processos de jeito nenhum.')
_tr7('guide.block.science', '役立つかもしれない理由', '为什么可能有帮助', 'Почему это может помочь', 'Por qué puede ayudar', 'Warum es helfen kann', 'Pourquoi ça peut aider', 'Por que pode ajudar')
_tr7('hr.ip_show', 'IP を表示', '显示 IP', 'Показать IP', 'Mostrar IP', 'IP zeigen', 'Afficher l’IP', 'Mostrar IP')
_tr7('hr.ip_hide', 'IP を隠す', '隐藏 IP', 'Скрыть IP', 'Ocultar IP', 'IP verbergen', 'Masquer l’IP', 'Ocultar IP')
_tr7('hr.ip_hidden_note', '配信やスクリーンショットに映らないよう、アドレスは隠しています。電話に入力するときは「IP を表示」をクリックしてください。', '我把地址隐藏起来，免得它出现在直播或截图里。点击“显示 IP”后，再把它抄到手机里。', 'Адрес я скрываю, чтобы его не было видно на стриме или скриншоте. В телефон его перепишешь, нажав «Показать IP».', 'Oculto la dirección para que no se vea en el stream ni en una captura de pantalla. Para escribirla en el móvil, pulsa «Mostrar IP».', 'Die Adresse verberge ich, damit sie weder im Stream noch auf einem Screenshot zu sehen ist. Ins Handy überträgst du sie nach einem Klick auf „IP zeigen“.', 'Je masque l’adresse pour qu’on ne la voie ni sur un stream ni sur une capture d’écran. Pour la recopier dans le téléphone, clique sur « Afficher l’IP ».', 'Escondo o endereço para que ele não apareça na stream nem em screenshots. Para digitá-lo no celular, clique em “Mostrar IP”.')
_tr7('hud.trigger_row.sub', '心拍パネルの下に、4つの合図のアイコンを表示します。見るためだけのもので、ゲーム中のビジュアルの代わりにはなりません — 合図には、ゲーム中のビジュアルが少なくともひとつオンになっている必要があります。', '心率面板下方会显示你四种提示的图标。它们只是用来看的，不能代替游戏中的视觉效果——提示至少需要打开其中一个视觉效果。', 'Под панелью с пульсом появятся значки твоих четырёх подсказок. Они только для вида и не заменяют визуалы в игре — для подсказки должен быть включён хотя бы один из них.', 'Bajo el panel de pulso aparecen los iconos de tus cuatro avisos. Son solo para verlos y no sustituyen a los visuales en el juego — un aviso necesita al menos uno de ellos activado.', 'Unter dem Puls-Panel erscheinen die Symbole deiner vier Hinweise. Sie sind nur zum Anschauen und ersetzen die Visuals im Spiel nicht — ein Hinweis braucht mindestens eins davon eingeschaltet.', 'Sous le panneau de pouls s’affichent les icônes de tes quatre rappels. Elles sont juste là pour l’œil et ne remplacent pas les visuels en jeu — un rappel a besoin qu’au moins l’un d’eux soit activé.', 'Embaixo do painel de pulso aparecem os ícones dos seus quatro avisos. Servem só para ver e não substituem os visuais no jogo — o aviso precisa de pelo menos um deles ativado.')
_tr7('log.hotkey_failed', 'ショートカット {combo} は別のアプリが使っているため、「今はいい」は使えません。私を黙らせるには、上のバーで停止してください — ただしそうすると、計測も止まります。', '快捷键 {combo} 被其他应用占用了，所以“现在不要”用不了。你仍然可以在顶部横条里停止我来让我安静——不过那样我也会停止测量。', 'Сочетание {combo} занято другим приложением, так что «не сейчас» не сработает. Заставить меня замолчать можно остановкой в полосе вверху — но тогда я перестану и измерять.', 'Otra aplicación está usando el atajo {combo}, así que «ahora no» no funcionará. Puedes silenciarme deteniéndome en la barra de arriba — pero entonces también dejo de medir.', 'Das Tastenkürzel {combo} ist von einer anderen Anwendung belegt, deshalb steht „Jetzt nicht“ nicht zur Verfügung. Stumm schalten kannst du mich, indem du mich in der Leiste oben stoppst — dann höre ich aber auch auf zu messen.', 'Une autre application occupe le raccourci {combo}, donc « pas maintenant » ne marchera pas. Tu peux me faire taire en m’arrêtant dans la barre en haut — mais alors j’arrête aussi de mesurer.', 'Outro aplicativo está usando o atalho {combo}, então o “agora não” não vai funcionar. Para me silenciar, você pode me parar na barra lá em cima — mas aí eu paro de medir também.')
_tr7('log.snooze_started', '今はいい：{minutes} 分間、声をかけません。監視は止まりません。', '现在不要：{minutes} 分钟内我不会出声。这不会停止监听。', 'Не сейчас: {minutes} мин я не подам голос. Слушать при этом не перестаю.', 'Ahora no: durante {minutes} minutos no aviso. La escucha sigue en marcha.', 'Jetzt nicht: {minutes} Minuten lang melde ich mich nicht. Das Zuhören läuft trotzdem weiter.', 'Pas maintenant : je ne me manifeste pas pendant {minutes} minutes. Ça n’arrête pas l’écoute.', 'Agora não: por {minutes} minutos não vou avisar. Isso não para a escuta.')
_tr7('dnes.trace_meta', '{time} · 合図 {n} 回', '{time} · 提示 {n} 次', '{time} · подсказки {n}×', '{time} · avisos {n}×', '{time} · Hinweise {n}×', '{time} · rappels {n}×', '{time} · avisos {n}×')
_tr7('log.edge_not_cached_later', 'Edge のセリフはまだ準備できていません — 今回は Windows の音声で話します。プレイ中は準備せず、監視を止めたときに準備します。', 'Edge 语音还没准备好——这次我先用 Windows 语音说。游戏过程中我不会准备它；等你停止监听时我再准备。', 'Фраза Edge ещё не готова — в этот раз говорю голосом Windows. Во время игры я её не готовлю; подготовлю, когда ты остановишь прослушивание.', 'La frase de Edge aún no está lista — esta vez hablo con la voz de Windows. Durante el juego no la preparo; la prepararé cuando detengas la escucha.', 'Die Edge-Zeile ist noch nicht bereit — diesmal spreche ich mit der Windows-Stimme. Während des Spiels bereite ich sie nicht vor; das mache ich, wenn du das Zuhören stoppst.', 'La réplique Edge n’est pas encore prête — cette fois, je parle avec la voix Windows. Je ne la prépare pas pendant le jeu ; je la préparerai quand tu arrêteras l’écoute.', 'A fala do Edge ainda não está pronta — desta vez falo com a voz do Windows. Durante o jogo eu não a preparo; vou prepará-la quando você parar a escuta.')
_tr7('settings.audio_reset_sub', '音量、バランス、話す速さが、アプリの初期値に戻ります。選んだ音声はそのままです。', '音量、比例和语速都会恢复为应用自带的默认值。已选的语音保持不变。', 'Громкость, баланс и скорость речи вернутся к значениям, с которыми приложение поставлялось. Выбранный голос останется.', 'El volumen, la mezcla y la velocidad del habla vuelven a los valores con los que venía la app. La voz elegida se mantiene.', 'Lautstärke, Verhältnis und Sprechtempo gehen auf die Werte zurück, mit denen die App ausgeliefert wurde. Die gewählte Stimme bleibt.', 'Le volume, l’équilibre et la vitesse de parole reviennent aux valeurs d’origine de l’app. La voix choisie reste.', 'O volume, a mistura e a velocidade da fala voltam aos valores de fábrica do app. A voz escolhida continua.')
_tr7('history.export_local', 'アプリは心拍もセッションもどこにも送りません — このコンピューターの中だけにあり、ファイルは好きな場所に保存できます。', '应用不会把你的心率和记录发送到任何地方——它们只在你的电脑里，文件保存在哪儿由你决定。', 'Пульс и сессии приложение никуда не отправляет — они только на твоём компьютере, а файл ты сохранишь, куда захочешь.', 'La app no envía tu pulso ni tus sesiones a ninguna parte — están solo en tu ordenador, y el archivo lo guardas donde quieras.', 'Puls und Sitzungen schickt die App nirgendwohin — sie sind nur auf deinem Rechner, und die Datei speicherst du, wo du willst.', 'L’app n’envoie ni ton pouls ni tes séances nulle part — ils restent seulement sur ton ordinateur, et tu enregistres le fichier où tu veux.', 'O app não envia o seu pulso nem as suas sessões para lugar nenhum — eles ficam só no seu computador, e você salva o arquivo onde quiser.')
_tr7('history.export_col.breathing', 'アプリからの合図', '应用发出的提示', 'Подсказки от приложения', 'Avisos de la app', 'Hinweise der App', 'Rappels de l’app', 'Avisos do app')
_tr7('history.export_col.signal', '信号 %', '信号 %', 'сигнал %', 'señal %', 'Signal %', 'signal %', 'sinal %')
_tr7('history.export_col.world', 'ワールド', '世界', 'мир', 'mundo', 'Welt', 'monde', 'mundo')
_tr7('history.export_col.dropouts', '心拍の途切れ', '心率中断', 'пропадания пульса', 'cortes de pulso', 'Puls-Ausfälle', 'coupures du pouls', 'quedas de sinal do pulso')
_tr7('history.export_col.blind_s', '信号なし (秒)', '无信号 (秒)', 'без сигнала (с)', 'sin señal (s)', 'ohne Signal (s)', 'sans signal (s)', 'sem sinal (s)')
_tr7('history.export_col.pause_episodes', '入力の休み', '输入停顿', 'паузы во вводе', 'pausas en la entrada', 'Eingabepausen', 'pauses d’entrée', 'pausas na entrada')
_tr7('tour.sensor.body', 'ここで、アプリにどこで聞けばいいかを伝えます。心拍を渡せば、負荷がしばらく高いまま続いたときに自分から合図を出します — ゲームに夢中なときに、あなたが思い出す必要はありません。時計がなければ、自分から声をかけることはありません。', '在这里告诉应用去哪里“听”你。把你的心率交给它，当你的负荷持续偏高一阵子时，它就会主动给你提示——你不必在激战中自己想起来。没有手表，它不会主动出声。', 'Здесь ты говоришь приложению, где тебя слушать. Если дашь ему свой пульс, оно само подаст подсказку, когда нагрузка какое-то время держится высокой, — тебе не нужно вспоминать об этом в пылу игры. Без часов оно само голос не подаст.', 'Aquí le dices a la app dónde tiene que escucharte. Cuando le das tu pulso, te avisa por sí sola cuando tu carga se mantiene alta un rato — no tienes que acordarte tú en pleno juego. Sin reloj no avisa por sí sola.', 'Hier sagst du der App, wo sie dir zuhören soll. Wenn du ihr deinen Puls gibst, meldet sie sich von selbst mit einem Hinweis, sobald deine Last eine Weile oben bleibt — du musst im Eifer des Spiels nicht selbst daran denken. Ohne Uhr meldet sie sich nicht von selbst.', 'Ici, tu dis à l’app où elle doit t’écouter. Quand tu lui donnes ton pouls, elle se manifeste d’elle-même avec un rappel quand ta charge reste haute un moment — tu n’as pas à y penser toi-même en plein jeu. Sans montre, elle ne se manifeste pas d’elle-même.', 'Aqui você diz ao app onde ele deve te ouvir. Se você der a ele o seu pulso, ele avisa por conta própria quando a sua carga fica alta por um tempo — você não precisa se lembrar disso no calor do jogo. Sem relógio, ele não avisa por conta própria.')
_tr7('hr.qr_ios', 'iPhone / Apple Watch\n「PulseOSC」（有料）。\nまだ試されていません。\nこの PC の IP とポートをその中で設定。', 'iPhone / Apple Watch\n“PulseOSC”（付费）。\n尚未测试。\n在其中设置这台电脑的 IP 和端口。', 'iPhone / Apple Watch\n«PulseOSC» (платно).\nПока не проверено.\nВнутри укажи IP и порт этого ПК.', 'iPhone / Apple Watch\n«PulseOSC» (de pago).\nAún no probado.\nDentro pon la IP y el puerto de este PC.', 'iPhone / Apple Watch\n„PulseOSC“ (kostenpflichtig).\nNoch nicht ausprobiert.\nDarin IP und Port dieses PCs eintragen.', 'iPhone / Apple Watch\n« PulseOSC » (payant).\nPas encore testé.\nY saisir l’IP et le port de ce PC.', 'iPhone / Apple Watch\n“PulseOSC” (pago).\nAinda não testado.\nNele, defina o IP e a porta deste PC.')
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
_tr7('kamae.lost_sub', '心拍が届かなくなりました（時計、電話、または Wi‑Fi）。戻るまでは何も計測せず、自分から声をかけることもありません。', '心率不再传过来了（手表、手机或 Wi‑Fi）。在它恢复之前，我什么都不测量，也不会主动出声。', 'Пульс перестал приходить (часы, телефон или Wi‑Fi). Пока он не вернётся, я ничего не измеряю и сама голос не подам.', 'El pulso dejó de llegar (reloj, móvil o Wi‑Fi). Hasta que vuelva, no mido nada ni aviso por mi cuenta.', 'Der Puls kommt nicht mehr an (Uhr, Handy oder WLAN). Bis er zurück ist, messe ich nichts und melde mich nicht von selbst.', 'Le pouls a cessé d’arriver (montre, téléphone ou Wi‑Fi). Tant qu’il n’est pas revenu, je ne mesure rien et je ne me manifeste pas de moi-même.', 'O pulso parou de chegar (relógio, celular ou Wi‑Fi). Até ele voltar, não meço nada e não aviso sozinha.')
_tr7('log.hr_back', '{s} 秒の途切れのあと、心拍が戻りました。', '无信号 {s} 秒后，心率恢复了。', 'Пульс вернулся после {s} с без сигнала.', 'El pulso ha vuelto tras {s} s sin señal.', 'Der Puls ist nach {s} s ohne Signal zurück.', 'Le pouls est revenu après {s} s sans signal.', 'O pulso voltou depois de {s} s sem sinal.')
_tr7('session.end.none_never', '負荷は一度もしきい値を超えませんでした — 声をかける理由がありませんでした。', '负荷一次都没有超过阈值——我没有理由出声。', 'Нагрузка ни разу не поднялась выше порога — мне не было повода подать голос.', 'La carga no superó el umbral ni una vez — no tenía por qué avisar.', 'Die Last ist kein einziges Mal über die Schwelle gekommen — ich hatte keinen Grund, mich zu melden.', 'La charge n’a pas une seule fois dépassé le seuil — je n’avais aucune raison de me manifester.', 'A carga não passou do limiar nem uma vez — eu não tinha motivo para avisar.')
_tr7('session.end.none_dropouts', '数えている最中に心拍が {n} 回途切れ、そのたびに数え直しになりました。心拍は時計から電話へ Bluetooth で、電話から PC へ Wi‑Fi で届きます — 時計は電話のそばに、電話は Wi‑Fi ルーターの近くに置いてください。', '心率有 {n} 次恰好在计时过程中中断，每次计时都得从头开始。心率从手表通过蓝牙传到手机，再从手机通过 Wi‑Fi 传到电脑——让手表靠近手机，手机靠近 Wi‑Fi 路由器。', 'Пульс {n}× пропадал как раз во время подсчёта, и подсчёт каждый раз начинался заново. Пульс идёт с часов на телефон по Bluetooth, а с телефона по Wi‑Fi на компьютер — держи часы рядом с телефоном, а телефон поближе к Wi‑Fi роутеру.', 'El pulso se cortó {n}× justo durante el conteo, y cada vez el conteo empezó de nuevo. El pulso va del reloj al móvil por Bluetooth y del móvil al PC por Wi‑Fi — ten el reloj cerca del móvil y el móvil cerca del router Wi‑Fi.', 'Der Puls ist {n}× genau während des Zählens ausgefallen, und das Zählen begann jedes Mal von vorn. Der Puls geht von der Uhr per Bluetooth zum Handy und vom Handy über WLAN zum PC — halte die Uhr beim Handy und das Handy nah am WLAN-Router.', 'Le pouls a décroché {n}× pile pendant le comptage, et le comptage a chaque fois recommencé à zéro. Le pouls passe de la montre au téléphone par Bluetooth, et du téléphone à l’ordinateur par Wi‑Fi — garde la montre près du téléphone et le téléphone près du routeur Wi‑Fi.', 'O sinal do pulso caiu {n}× justamente durante a contagem, e a contagem recomeçou do zero toda vez. O pulso vai do relógio para o celular por Bluetooth, e do celular para o PC por Wi‑Fi — mantenha o relógio perto do celular e o celular perto do roteador Wi‑Fi.')
_tr7('session.end.none_nopause', 'ずっと、入力の休みを一度もとらえられませんでした — キーボード、マウス、コントローラーから数秒離れることさえも。声をかける前に待っているのは、まさにその休みです。何かが休みなく入力を送っているのかもしれません。たとえばコントローラーのモーションセンサー（ジャイロ）や、デッドゾーンのないスティック。コントローラーでプレイしているなら、ジャイロをオフにしてみてください。', '整个过程中，我一次输入停顿都没捕捉到——连几秒钟不碰键盘、鼠标或手柄的时候都没有。而我正是要等这样的停顿才出声。可能有东西在不间断地报告输入，比如手柄的体感传感器（陀螺仪）或者没有死区的摇杆。如果你用手柄玩，试试把它的陀螺仪关掉。', 'Всё это время я не поймала ни одной паузы во вводе — даже нескольких секунд без клавиатуры, мыши или геймпада. А именно её я жду, прежде чем подать голос. Возможно, что-то сообщает о вводе без перерыва, например датчик движения геймпада (гироскоп) или стик без мёртвой зоны. Если играешь с геймпадом, попробуй выключить в нём гироскоп.', 'En todo el rato no detecté ni una sola pausa en la entrada — ni unos segundos sin teclado, ratón o mando. Y es justo lo que espero antes de avisar. Puede que algo esté enviando entrada sin parar, por ejemplo el sensor de movimiento del mando (giroscopio) o un stick sin zona muerta. Si juegas con mando, prueba a desactivarle el giroscopio.', 'Die ganze Zeit habe ich keine einzige Pause in deiner Eingabe erwischt — nicht mal ein paar Sekunden ohne Tastatur, Maus oder Controller. Und genau darauf warte ich, bevor ich mich melde. Vielleicht sendet etwas ununterbrochen Eingaben, zum Beispiel der Bewegungssensor des Controllers (Gyro) oder ein Stick ohne Deadzone. Wenn du mit Controller spielst, probier, das Gyro darin auszuschalten.', 'Pendant tout ce temps, je n’ai pas capté une seule pause dans tes entrées — pas même quelques secondes sans clavier, souris ou manette. Et c’est justement elle que j’attends avant de me manifester. Quelque chose signale peut-être des entrées sans arrêt, par exemple le capteur de mouvement de la manette (gyro) ou un stick sans zone morte. Si tu joues à la manette, essaie d’y désactiver le gyro.', 'O tempo todo não detectei nenhuma pausa na entrada — nem alguns segundos sem teclado, mouse ou controle. E é justamente por ela que eu espero antes de avisar. Talvez algo esteja registrando entrada sem parar, como o sensor de movimento do controle (giroscópio) ou um analógico sem zona morta. Se você joga com controle, tente desativar o giroscópio dele.')
_tr7('session.end.none_withheld', '負荷は十分長く高いままでしたが、ちょうどいい瞬間が来ませんでした — まだ上がり続けていたか、心拍が「ピーク」の帯にありました。黙っているほうを選びました。', '负荷持续偏高的时间已经够长了，但合适的时机一直没来——要么它还在上升，要么心率处于高峰区间。我宁可保持安静。', 'Нагрузка держалась высокой достаточно долго, но подходящий момент так и не настал — она либо ещё росла, либо пульс был в пиковой зоне. Я предпочла промолчать.', 'La carga estuvo alta bastante tiempo, pero no llegó el momento adecuado — o aún subía, o el pulso estaba en la zona de pico. Preferí quedarme callada.', 'Die Last war lange genug oben, aber der passende Moment kam nicht — entweder stieg sie noch, oder dein Puls war im Spitzenbereich. Ich habe lieber geschwiegen.', 'La charge est restée haute assez longtemps, mais le bon moment n’est pas venu — soit elle montait encore, soit ton pouls était en zone de pic. J’ai préféré me taire.', 'A carga ficou alta por tempo suficiente, mas o momento certo não chegou — ou ela ainda estava subindo, ou o pulso estava na zona de pico. Preferi ficar calada.')
_tr7('data.hint', '心拍、セッション、気づきはこのコンピューターに残ります。設定も同じです — ただし合図の文面は別です。自然な音声（Edge、既定）で話すとき、アプリは音声に変換するためにその文面を Microsoft に送ります。Windows の音声は何も送りません。', '你的心率、记录和分析结论都留在这台电脑上。设置也是，只有提示的文字例外：当提示用自然语音（Edge，默认）朗读时，应用会把它们的文字发送给 Microsoft 的服务转换成语音。Windows 语音不会发送任何东西。', 'Твой пульс, сессии и наблюдения остаются на этом компьютере. Настройки тоже, кроме текста подсказок: когда они звучат естественным голосом (Edge, по умолчанию), приложение отправляет их текст сервису Microsoft для преобразования в речь. Голос Windows ничего не отправляет.', 'Tu pulso, tus sesiones y las observaciones se quedan en este ordenador. Los ajustes también, salvo el texto de los avisos: cuando hablan con la voz natural (Edge, la predeterminada), la app envía su texto al servicio de Microsoft para convertirlo en voz. La voz de Windows no envía nada.', 'Dein Puls, deine Sitzungen und Beobachtungen bleiben auf diesem Rechner. Die Einstellungen auch, bis auf den Text der Hinweise: Wenn sie mit der natürlichen Stimme sprechen (Edge, Standard), schickt die App ihren Text an Microsoft, um ihn in Sprache umzuwandeln. Die Windows-Stimme schickt nichts.', 'Ton pouls, tes séances et les observations restent sur cet ordinateur. Les réglages aussi, sauf le texte des rappels : quand ils parlent avec la voix naturelle (Edge, par défaut), l’app envoie leur texte au service Microsoft pour le convertir en parole. La voix Windows n’envoie rien.', 'O seu pulso, as sessões e as observações ficam neste computador. As configurações também, exceto o texto dos avisos: quando eles falam com a voz natural (Edge, a padrão), o app envia o texto deles ao serviço da Microsoft para convertê-lo em fala. A voz do Windows não envia nada.')
_tr7('data.delete.legacy', '古いバージョンのアプリが残したコピー（フォルダー「{folder}」）', '旧版应用留下的副本（文件夹“{folder}”）', 'копии от старой версии приложения (папка «{folder}»)', 'copias de una versión anterior de la app (carpeta «{folder}»)', 'Kopien aus einer älteren Version der App (Ordner „{folder}“)', 'copies d’une ancienne version de l’app (dossier « {folder} »)', 'cópias de uma versão mais antiga do app (pasta “{folder}”)')
_tr7('data.export.btn', '履歴をエクスポート（JSON）', '导出历史（JSON）', 'Экспортировать историю (JSON)', 'Exportar historial (JSON)', 'Verlauf exportieren (JSON)', 'Exporter l’historique (JSON)', 'Exportar histórico (JSON)')
_tr7('data.import.flagged', 'インポートした記録には、あなたのものではないという印がつきます。「履歴」には表示されますが、アプリはそこから学びません。安静時ベースライン、高心拍のしきい値、私が声をかけるしきい値、気づき、合図のグラフ、前回のセッションのカード、そして私が音声で声をかけるか、ビジュアルで知らせるか、休むかの判断には入りません。別のコンピューターからのあなた自身のエクスポートでも同じです。', '导入的记录会被标记为“外来”。你能在“历史”里看到它们，但应用不会从中学习：它们不会计入你的静息基线、高心率阈值和我出声所依据的负荷阈值，也不会进入分析结论、提示图表、最近一次记录的卡片，也不会影响我是用语音、画面提示还是暂停提示。你自己从另一台电脑导出的数据也是如此。', 'Импортированные записи помечаются как чужие. В «Истории» ты их увидишь, но приложение на них не учится: они не входят ни в твою базовую линию покоя, ни в порог высокого пульса, ни в порог, от которого я подаю голос, ни в наблюдения, ни в график о подсказках, ни в карточку последней сессии, ни в выбор, подаю ли я голос, показываю картинку или беру паузу. Это касается и твоего собственного экспорта с другого компьютера.', 'Los registros importados se marcarán como ajenos. Los verás en el Historial, pero la app no aprende de ellos: no entran en tu línea base en reposo, ni en el límite de pulso alto, ni en el umbral a partir del cual aviso, ni en las observaciones, el gráfico de avisos o la tarjeta de la última sesión, ni en si aviso con voz, con imagen o me tomo una pausa. Esto vale también para tu propia exportación desde otro ordenador.', 'Importierte Einträge werden als fremd markiert. Im Verlauf siehst du sie, aber die App lernt nicht aus ihnen: Sie fließen weder in deine Ruhebasislinie noch in deine Grenze für hohen Puls oder die Schwelle ein, ab der ich mich melde, auch nicht in die Beobachtungen, das Diagramm zu den Hinweisen, die Karte der letzten Sitzung und nicht in die Entscheidung, ob ich mich mit Stimme oder Bild melde oder eine Pause einlege. Das gilt auch für deinen eigenen Export von einem anderen Rechner.', 'Les enregistrements importés sont marqués comme étrangers. Tu les verras dans l’Historique, mais l’app n’en apprend rien : ils n’entrent ni dans ta ligne de base au repos, ni dans ton seuil de pouls élevé, ni dans le seuil à partir duquel je me manifeste, ni dans les observations, le graphique des rappels ou la carte de la dernière séance, ni dans le choix de me manifester par la voix, par l’image ou de faire une pause. Cela vaut aussi pour ton propre export depuis un autre ordinateur.', 'Os registros importados são marcados como externos. Você vai vê-los no Histórico, mas o app não aprende com eles: não entram na sua linha de base em repouso, no seu limite de pulso alto nem no limiar a partir do qual eu aviso, nas observações, no gráfico dos avisos, no cartão da última sessão, nem na decisão de eu avisar com voz, com imagem ou fazer uma pausa. Isso vale também para uma exportação sua de outro computador.')
_tr7('data.import.question', 'あなたのものと統合しますか？ それとも、これで置き換えますか？', '把它们和你的合并，还是用它们替换你的？', 'Объединить их с твоими или заменить ими твои?', '¿Combinarlos con los tuyos o reemplazar los tuyos por ellos?', 'Mit deinen zusammenführen oder deine durch sie ersetzen?', 'Les fusionner avec les tiens, ou remplacer les tiens par eux ?', 'Juntar com os seus ou substituir os seus por eles?')
_tr7('data.import.replace_confirm', '置き換えると、セッション履歴と測定ウィンドウがファイルの内容で上書きされます。その前に、元のファイルの隣にバックアップとして取っておきます（名前に「pred-importom」が入ります）。本当に置き換えますか？', '替换会用文件内容覆盖你的记录历史和测量窗口。在此之前，我会把它们作为备份放在原文件旁边（文件名中带有“pred-importom”）。确定要替换吗？', 'Замена перезапишет твою историю сессий и измерительные окна содержимым файла. Перед этим я отложу их как резервную копию рядом с исходными файлами (с «pred-importom» в названии). Точно заменить?', 'Reemplazar sobrescribe tu historial de sesiones y las ventanas de medición con el contenido del archivo. Antes los guardaré como copia de seguridad junto a los archivos originales (con «pred-importom» en el nombre). ¿Reemplazar de verdad?', 'Beim Ersetzen werden dein Sitzungsverlauf und die Messfenster mit dem Inhalt der Datei überschrieben. Vorher lege ich sie als Sicherung neben die ursprünglichen Dateien (mit „pred-importom“ im Namen). Wirklich ersetzen?', 'Remplacer écrase ton historique des séances et tes fenêtres de mesure avec le contenu du fichier. Avant ça, je les mets de côté comme sauvegarde à côté des fichiers d’origine (avec « pred-importom » dans le nom). Vraiment remplacer ?', 'Substituir sobrescreve o seu histórico de sessões e as janelas de medição com o conteúdo do arquivo. Antes disso, eu os guardo como cópia de segurança ao lado dos arquivos originais (com “pred-importom” no nome). Substituir mesmo?')
_tr7('data.import.replace_yes', 'はい、置き換える', '是，替换', 'Да, заменить', 'Sí, reemplazar', 'Ja, ersetzen', 'Oui, remplacer', 'Sim, substituir')
_tr7('data.import.back', '戻る', '返回', 'Назад', 'Atrás', 'Zurück', 'Retour', 'Voltar')
_tr7('data.import.backup', '元のファイルをバックアップとして取っておきました：{files}', '我已把原文件作为备份保存：{files}', 'Исходные файлы я отложила как резервную копию: {files}', 'He guardado los archivos originales como copia de seguridad: {files}', 'Die ursprünglichen Dateien habe ich als Sicherung beiseitegelegt: {files}', 'J’ai mis les fichiers d’origine de côté comme sauvegarde : {files}', 'Guardei os arquivos originais como cópia de segurança: {files}')
_tr7('world.play', 'ゲーム', '游戏', 'Игра', 'Juego', 'Spiel', 'Jeu', 'Jogo')
_tr7('world.work', '仕事', '工作', 'Работа', 'Trabajo', 'Arbeit', 'Travail', 'Trabalho')
_tr7('world.tip', 'ワールド：ゲームか仕事か — それぞれに独自の履歴と見た目があります。\n仕事中はビジュアルだけで知らせます。進行中のセッションは、始まったワールドにとどまります。', '世界：游戏或工作——各自有独立的历史和外观。\n工作时我只用画面提示。进行中的记录会留在它开始时所在的世界。', 'Мир: игра или работа — у каждого своя история и внешний вид.\nНа работе я даю о себе знать только картинкой. Идущая сессия остаётся в мире, в котором началась.', 'Mundo: juego o trabajo — cada uno tiene su propio historial y aspecto.\nEn el trabajo solo aviso con imagen. Una sesión en curso se queda en el mundo en el que empezó.', 'Welt: Spiel oder Arbeit — jede hat ihren eigenen Verlauf und ihr eigenes Aussehen.\nBei der Arbeit melde ich mich nur mit Bild. Eine laufende Sitzung bleibt in der Welt, in der sie begonnen hat.', 'Monde : jeu ou travail — chacun a son propre historique et son apparence.\nAu travail, je ne me manifeste que par l’image. Une séance en cours reste dans le monde où elle a commencé.', 'Mundo: jogo ou trabalho — cada um tem o próprio histórico e a própria aparência.\nNo Trabalho, só aviso com imagem. Uma sessão em andamento fica no mundo em que começou.')
_tr7('settings.world', 'ワールド', '世界', 'Мир', 'Mundo', 'Welt', 'Monde', 'Mundo')
_tr7('settings.world_sub', 'ゲームは Sumi、仕事は Aizome。ワールドごとに独自の履歴と気づきがあります。仕事中はビジュアルだけで知らせます — 音声も効果音もなし。安静時ベースラインは共通です — 体はひとつですから。高心拍のしきい値と負荷のしきい値は、ゲームからだけ算出します。', '游戏是 Sumi，工作是 Aizome。每个世界都有自己的历史和分析结论。工作时我只用画面提示——没有语音和音效。静息基线是共用的，毕竟身体只有一个；高心率阈值和负荷阈值我只根据游戏计算。', 'Игра — это Sumi, работа — Aizome. У каждого мира своя история и наблюдения. На работе я даю о себе знать только картинкой — без голоса и звука. Базовая линия покоя общая, тело ведь одно; порог высокого пульса и порог нагрузки я считаю только по игре.', 'El juego es Sumi; el trabajo, Aizome. Cada mundo tiene su propio historial y sus observaciones. En el trabajo solo aviso con imagen — sin voz ni sonido. La línea base en reposo es común, el cuerpo es uno; el límite de pulso alto y el de carga los calculo solo a partir del juego.', 'Spiel ist Sumi, Arbeit ist Aizome. Jede Welt hat ihren eigenen Verlauf und eigene Beobachtungen. Bei der Arbeit melde ich mich nur mit Bild — ohne Stimme und Ton. Die Ruhebasislinie ist gemeinsam, es ist ein Körper; die Grenzen für hohen Puls und für die Last berechne ich nur aus dem Spielen.', 'Le jeu, c’est Sumi ; le travail, Aizome. Chaque monde a son propre historique et ses observations. Au travail, je ne me manifeste que par l’image — sans voix ni son. La ligne de base au repos est commune, le corps est le même ; le seuil de pouls élevé comme celui de la charge, je ne les calcule qu’à partir du jeu.', 'Jogo é Sumi, Trabalho é Aizome. Cada mundo tem o próprio histórico e as próprias observações. No Trabalho, só aviso com imagem — sem voz e sem som. A linha de base em repouso é compartilhada, o corpo é um só; o limite de pulso alto e o limiar de carga eu calculo só a partir do jogo.')
_tr7('history.world_note', 'ワールド：{world}。ラベルのない古いセッションは「ゲーム」に入ります。「{chart}」グラフは、ゲームで鳴った合図だけを数えます — 仕事中はビジュアルだけで知らせるからです。', '世界：{world}。没有标签的旧记录归入“游戏”。“{chart}”图表只统计游戏中出声的提示——工作时我只用画面提示。', 'Мир: {world}. Старые сессии без метки относятся к «Игре». График «{chart}» учитывает только прозвучавшие подсказки из игры — на работе я даю о себе знать только картинкой.', 'Mundo: {world}. Las sesiones antiguas sin etiqueta pertenecen a Juego. El gráfico «{chart}» cuenta solo los avisos del juego que sonaron — en el trabajo solo aviso con imagen.', 'Welt: {world}. Ältere Sitzungen ohne Kennzeichnung gehören zur Welt Spiel. Das Diagramm „{chart}“ zählt nur Hinweise aus dem Spiel, die erklungen sind — bei der Arbeit melde ich mich nur mit Bild.', 'Monde : {world}. Les anciennes séances sans étiquette appartiennent au Jeu. Le graphique « {chart} » ne compte que les rappels du jeu qui ont retenti — au travail, je ne me manifeste que par l’image.', 'Mundo: {world}. Sessões antigas sem rótulo contam como Jogo. O gráfico “{chart}” conta só os avisos do Jogo que tocaram — no Trabalho, só aviso com imagem.')
_tr7('ob.step4.title', 'メインのワールドを選ぶ', '选择你的主世界', 'Выбери основной мир', 'Elige tu mundo principal', 'Wähle deine Hauptwelt', 'Choisis ton monde principal', 'Escolha o seu mundo principal')
_tr7('ob.step4.body', '右上でいつでも切り替えられます。ワールドごとに独自の履歴と見た目があります。', '随时可以在右上角切换。每个世界都有自己的历史和外观。', 'Переключить его можно когда угодно справа вверху. У каждого мира своя история и внешний вид.', 'Lo cambias cuando quieras arriba a la derecha. Cada mundo tiene su propio historial y aspecto.', 'Du kannst sie jederzeit oben rechts wechseln. Jede Welt hat ihren eigenen Verlauf und ihr eigenes Aussehen.', 'Tu le changes à tout moment en haut à droite. Chaque monde a son propre historique et son apparence.', 'Dá para trocar a qualquer momento no canto superior direito. Cada mundo tem o próprio histórico e a própria aparência.')
_tr7('ob.world.play.title', 'ゲーム · 墨 Sumi', '游戏 · 墨 Sumi', 'Игра · 墨 Sumi', 'Juego · 墨 Sumi', 'Spiel · 墨 Sumi', 'Jeu · 墨 Sumi', 'Jogo · 墨 Sumi')
_tr7('ob.world.play.desc', 'プレイするとき。合間に合図、たいていは音声つき。\n墨に金。', '玩游戏时。提示出现在间歇里，大多带语音。\n墨与金。', 'Когда играешь. Подсказки в паузах, чаще с голосом.\nТушь с золотом.', 'Cuando juegas. Avisos en las pausas, casi siempre con voz.\nTinta con oro.', 'Wenn du spielst. Hinweise in den Pausen, meist mit Stimme.\nTinte mit Gold.', 'Quand tu joues. Des rappels dans les pauses, surtout avec la voix.\nEncre et or.', 'Para quando você joga. Avisos nas pausas, geralmente com voz.\nNanquim com ouro.')
_tr7('ob.world.work.title', '仕事 · 藍 Aizome', '工作 · 藍 Aizome', 'Работа · 藍 Aizome', 'Trabajo · 藍 Aizome', 'Arbeit · 藍 Aizome', 'Travail · 藍 Aizome', 'Trabalho · 藍 Aizome')
_tr7('ob.world.work.desc', '仕事をするとき。合図はビジュアルだけ、音声も効果音もなし。\n藍色。', '工作时。提示只用画面，没有语音和音效。\n靛蓝。', 'Когда работаешь. Подсказки только картинкой, без голоса и звука.\nИндиго.', 'Cuando trabajas. Avisos solo con imagen, sin voz ni sonido.\nÍndigo.', 'Wenn du arbeitest. Hinweise nur als Bild, ohne Stimme und Ton.\nIndigo.', 'Quand tu travailles. Des rappels seulement en image, sans voix ni son.\nIndigo.', 'Para quando você trabalha. Avisos só com imagem, sem voz e sem som.\nÍndigo.')
_tr7('session.end.title_work', '{time} 仕事をした。', '你工作了 {time}。', 'Ты работал {time}.', 'Trabajaste {time}.', 'Du hast {time} gearbeitet.', 'Tu as travaillé {time}.', 'Você trabalhou por {time}.')
_tr7('session.end.cues_work', '{n} 回合図を出した — 仕事中なので、ビジュアルだけで音声も効果音もなし。', '我提醒了 {n} 次——工作时只用画面，没有语音和音效。', 'Я дала о себе знать {n}× — на работе только картинкой, без голоса и звука.', 'Te avisé {n} veces — en el trabajo solo con imagen, sin voz ni sonido.', 'Ich habe mich {n}× gemeldet — bei der Arbeit nur mit Bild, ohne Stimme und Ton.', 'Je me suis manifestée {n}× — au travail seulement par l’image, sans voix ni son.', 'Avisei {n}× — no Trabalho, só com imagem, sem voz e sem som.')
_tr7('settings.hr_critical_computed', 'あなたの高心拍のしきい値：{bpm} BPM — あなたのゲームのセッション {n} 回から算出。設定するものではなく、アプリがあなたを知るにつれて調整します。', '你的高心率阈值：{bpm} BPM——根据你的 {n} 次游戏记录计算得出。它不需要设置，应用会随着对你的了解调整它。', 'Твой порог высокого пульса: {bpm} BPM — вычислен по твоим игровым сессиям ({n}). Это не настройка: приложение уточнит его, по мере того как узнает тебя.', 'Tu límite de pulso alto: {bpm} BPM — calculado a partir de {n} de tus sesiones de juego. No se ajusta; la app lo irá adaptando a medida que te conozca.', 'Deine Grenze für hohen Puls: {bpm} BPM — berechnet aus {n} deiner Spielsitzungen. Sie wird nicht eingestellt; die App passt sie an, während sie dich kennenlernt.', 'Ton seuil de pouls élevé : {bpm} BPM — calculé à partir de {n} de tes séances de jeu. Il ne se règle pas, l’app l’ajuste à mesure qu’elle te connaît.', 'O seu limite de pulso alto: {bpm} BPM — calculado a partir de {n} das suas sessões de jogo. Não é uma configuração; o app o ajusta conforme vai te conhecendo.')
_tr7('settings.hr_critical_learning', '今のところ {bpm} BPM で計算しています。あと {treba} 回ゲームのセッションをすれば、あなた自身のしきい値を算出します — 設定することは何もありません。', '目前我先按 {bpm} BPM 计算。再有 {treba} 次游戏记录后，我会算出你自己的阈值——你什么都不用设置。', 'Пока я исхожу из {bpm} BPM. Твой собственный порог я вычислю после ещё нескольких игровых сессий (осталось: {treba}) — настраивать ничего не нужно.', 'Por ahora cuento con {bpm} BPM. Calcularé tu propio límite tras {treba} sesiones de juego más — no tienes que ajustar nada.', 'Vorerst rechne ich mit {bpm} BPM. Deine eigene Grenze berechne ich nach {treba} weiteren Spielsitzungen — du musst nichts einstellen.', 'Pour l’instant, je me base sur {bpm} BPM. Je calculerai ton propre seuil après {treba} séances de jeu de plus — tu n’as rien à régler.', 'Por enquanto uso {bpm} BPM. Vou calcular o seu próprio limite depois de mais {treba} sessões de jogo — você não precisa configurar nada.')
_tr7('cue_rate.computed', '負荷が {prah} を超えた状態が {hold} 秒続いたら声をかけます — このしきい値は、あなたのゲームのセッション {n} 回から、プレイ時間の5分の1をそれより上で過ごす水準として算出しました。多くても1時間に {strop} 回、間隔は少なくとも {odstup} 分。', '当你的负荷在 {prah} 以上保持 {hold} 秒时，我会出声——这条线是我根据你的 {n} 次游戏记录算出来的：你有五分之一的游戏时间处在它之上。每小时最多 {strop} 次，间隔至少 {odstup} 分钟。', 'Я подаю голос, когда твоя нагрузка держится {hold} с выше {prah}, — этот порог я вычислила по твоим игровым сессиям ({n}) как уровень, выше которого ты проводишь пятую часть игры. Не чаще {strop}× в час, с промежутком не меньше {odstup} мин.', 'Aviso cuando tu carga se mantiene {hold} s por encima de {prah} — ese umbral lo calculé a partir de {n} de tus sesiones de juego como el nivel por encima del cual pasas una quinta parte del tiempo de juego. Como mucho {strop}× por hora, con al menos {odstup} min de separación.', 'Ich melde mich, wenn deine Last {hold} s über {prah} bleibt — diese Schwelle habe ich aus {n} deiner Spielsitzungen berechnet, als das Niveau, über dem du ein Fünftel deiner Spielzeit verbringst. Höchstens {strop}× pro Stunde, mit mindestens {odstup} Min Abstand.', 'Je me manifeste quand ta charge reste {hold} s au-dessus de {prah} — ce seuil, je l’ai calculé à partir de {n} de tes séances de jeu comme le niveau au-dessus duquel tu passes un cinquième de ton temps de jeu. Au plus {strop}× par heure, avec au moins {odstup} min d’écart.', 'Eu aviso quando a sua carga se mantém {hold} s acima de {prah} — calculei esse limiar a partir de {n} das suas sessões de jogo como o nível acima do qual você passa um quinto do tempo de jogo. No máximo {strop}× por hora, com intervalo de pelo menos {odstup} min.')
_tr7('cue_rate.learning', '今のところは平均的なプレイヤー向けの数値を使っています。負荷が {prah} を超えた状態が {hold} 秒続いたら声をかけます。あなた自身のしきい値はゲームのセッションから算出します — 設定することは何もありません。', '目前我先用普通玩家的数值：当负荷在 {prah} 以上保持 {hold} 秒时，我会出声。你自己的阈值我会根据你的游戏记录来算——你什么都不用设置。', 'Пока я исхожу из чисел для среднего игрока: подаю голос, когда нагрузка держится {hold} с выше {prah}. Собственный порог я вычислю по твоим игровым сессиям — настраивать ничего не нужно.', 'Por ahora uso los números de un jugador medio: aviso cuando la carga se mantiene {hold} s por encima de {prah}. Tu propio umbral lo calcularé a partir de tus sesiones de juego — no tienes que ajustar nada.', 'Vorerst rechne ich mit Zahlen für einen durchschnittlichen Spieler: Ich melde mich, wenn die Last {hold} s über {prah} bleibt. Deine eigene Schwelle berechne ich aus deinen Spielsitzungen — du musst nichts einstellen.', 'Pour l’instant, je me base sur les chiffres d’un joueur moyen : je me manifeste quand la charge reste {hold} s au-dessus de {prah}. Je calculerai ton propre seuil à partir de tes séances de jeu — tu n’as rien à régler.', 'Por enquanto uso números de um jogador médio: aviso quando a carga se mantém {hold} s acima de {prah}. O seu próprio limiar eu calculo a partir das suas sessões de jogo — você não precisa configurar nada.')
_tr7('session.felt.cue.agitated', 'かき乱された', '让我烦躁', 'взвинтила меня', 'me alteró', 'hat mich aufgewühlt', 'm’a énervé', 'me tirou do eixo')
_tr7('history.rebrik.visual', '今はビジュアルだけで知らせていて、音は出していません。{dovod} 合図のあったセッションが不満なく続いたら、音を戻します（あと {n} 回必要）。', '现在我只用画面提示，没有声音。{dovod} 等之后几次有提示的记录都没有异议时，我会恢复声音（还需要：{n} 次）。', 'Сейчас я даю о себе знать только картинкой, без звука. {dovod} Звук верну, когда следующие сессии с подсказкой пройдут без нареканий (нужно ещё: {n}).', 'Por ahora solo aviso con imagen, sin sonido. {dovod} Devolveré el sonido cuando más sesiones con aviso pasen sin quejas (faltan: {n}).', 'Im Moment melde ich mich nur mit Bild, ohne Ton. {dovod} Den Ton bringe ich zurück, wenn weitere Sitzungen mit Hinweis ohne Einwände vergehen (noch nötig: {n}).', 'Pour l’instant, je ne me manifeste que par l’image, sans son. {dovod} Je remettrai le son quand d’autres séances avec un rappel se seront passées sans objection (encore nécessaires : {n}).', 'Por enquanto só aviso com imagem, sem som. {dovod} Trago o som de volta quando mais sessões com aviso passarem sem queixas (ainda faltam: {n}).')
_tr7('history.rebrik.pause', '今は合図をオフにしています。{dovod} 5分以上のセッションをあと何回か重ねたら、ビジュアルでもう一度試します（あと {n} 回必要）。合図がなくて物足りなければ、セッション後のアンケートで「はい、あった」と答えてください。次のセッションからまた試します。', '我现在关闭了提示。{dovod} 再有几次至少 5 分钟的记录后，我会用画面再试一次（还需要：{n} 次）。如果你想念这些提示，就在记录结束后的问卷里选“有，该提醒”，从下一次记录起我会再试。', 'Подсказки у меня сейчас выключены. {dovod} Картинкой попробую снова после следующих сессий хотя бы по 5 минут (нужно ещё: {n}). Если тебе не хватает подсказок, в опросе после сессии ответь «да, стоило» — и со следующей сессии я попробую снова.', 'Ahora tengo los avisos desactivados. {dovod} Volveré a probar con imagen tras más sesiones de al menos 5 minutos (faltan: {n}). Si echas de menos los avisos, responde «sí, debió» en el cuestionario tras la sesión y lo volveré a intentar desde la siguiente.', 'Die Hinweise habe ich im Moment ausgeschaltet. {dovod} Mit Bild probiere ich es wieder nach weiteren Sitzungen von mindestens 5 Minuten (noch nötig: {n}). Wenn dir die Hinweise fehlen, antworte im Fragebogen nach der Sitzung „ja, hätte sollen“, und ab der nächsten Sitzung probiere ich es wieder.', 'Les rappels sont désactivés pour l’instant. {dovod} Je réessaierai avec l’image après d’autres séances d’au moins 5 minutes (encore nécessaires : {n}). Si les rappels te manquent, réponds « oui, il aurait dû » dans le questionnaire après la séance, et je réessaierai dès la suivante.', 'Os avisos estão desativados por enquanto. {dovod} Vou tentar de novo com imagem depois de mais sessões de pelo menos 5 minutos (ainda faltam: {n}). Se você sente falta dos avisos, responda “sim, devia” no questionário depois da sessão e eu tento de novo a partir da próxima.')
_tr7('history.rebrik.why.disruptive', 'セッション後のアンケートで、合図が邪魔だったと答えました。', '你在记录结束后的问卷里说提示打扰到你了。', 'После сессии ты написал в опросе, что подсказка мешала.', 'Tras una sesión, dijiste en el cuestionario que el aviso molestó.', 'Nach einer Sitzung hast du im Fragebogen angegeben, dass der Hinweis gestört hat.', 'Après une séance, tu as écrit dans le questionnaire que le rappel avait gêné.', 'Depois de uma sessão, você disse no questionário que o aviso atrapalhou.')
_tr7('history.rebrik.why.agitated', 'セッション後のアンケートで、合図にかき乱されたと答えました。', '你在记录结束后的问卷里说提示让你烦躁。', 'После сессии ты написал в опросе, что подсказка тебя взвинтила.', 'Tras una sesión, dijiste en el cuestionario que el aviso te alteró.', 'Nach einer Sitzung hast du im Fragebogen angegeben, dass dich der Hinweis aufgewühlt hat.', 'Après une séance, tu as écrit dans le questionnaire que le rappel t’avait énervé.', 'Depois de uma sessão, você disse no questionário que o aviso te tirou do eixo.')
_tr7('history.rebrik.why.snooze', '合図から1分以内に私を静かにさせ、そのあともセッションが続きました。', '提示后一分钟内你就让我静音了，而记录之后还在继续。', 'В течение минуты после подсказки ты меня заглушил, а сессия потом ещё продолжалась.', 'Me silenciaste en el minuto siguiente a un aviso, y después la sesión continuó.', 'Innerhalb einer Minute nach einem Hinweis hast du mich stummgeschaltet, und die Sitzung ging danach noch weiter.', 'Moins d’une minute après un rappel, tu m’as mise en sourdine, et la séance a ensuite continué.', 'Você me silenciou menos de um minuto depois de um aviso, e a sessão continuou depois disso.')
_tr7('history.rebrik.why.retry', '静かなセッションを何回か経たので、もう一度試しています。', '安静了几次记录之后，我再试一次。', 'После нескольких тихих сессий пробую снова.', 'Tras unas sesiones de silencio, lo vuelvo a intentar.', 'Nach ein paar stillen Sitzungen versuche ich es wieder.', 'Après quelques séances de silence, je réessaie.', 'Depois de algumas sessões em silêncio, estou tentando de novo.')
_tr7('history.rebrik.why.missed', '私が声をかけるべきだったと答えてくれたので、もう一度試しています。', '你说我当时应该出声，所以我再试一次。', 'Ты написал, что мне стоило подать голос, — вот и пробую снова.', 'Dijiste que debí avisar, así que lo vuelvo a intentar.', 'Du hast angegeben, dass ich mich hätte melden sollen, also versuche ich es wieder.', 'Tu as écrit que j’aurais dû me manifester, alors je réessaie.', 'Você disse que eu devia ter avisado, então estou tentando de novo.')
_tr7('session.end.cues_visual', '{n} 回合図を出した — ビジュアルだけで、音はなし。', '我提醒了 {n} 次——只用画面，没有声音。', 'Я дала о себе знать {n}× — только картинкой, без звука.', 'Te avisé {n} veces — solo con imagen, sin sonido.', 'Ich habe mich {n}× gemeldet — nur mit Bild, ohne Ton.', 'Je me suis manifestée {n}× — seulement par l’image, sans son.', 'Avisei {n}× — só com imagem, sem som.')
_tr7('session.end.none_paused', 'あなたのフィードバックを受けて、数回のセッションのあいだ合図をオフにしています — 理由は「履歴」にあります。合図がなくて物足りなければ、下で「はい、あった」と答えてください。', '根据你的反馈，我把提示关闭了几次记录——原因可以在“历史”里找到。如果你想念它们，就在下面选“有，该提醒”。', 'После твоего отзыва я выключила подсказки на несколько сессий — почему, найдёшь в «Истории». Если тебе их не хватает, ответь ниже «да, стоило».', 'Tras tu respuesta, tengo los avisos desactivados durante unas sesiones — el porqué está en el Historial. Si los echas de menos, responde abajo «sí, debió».', 'Nach deinem Feedback habe ich die Hinweise für ein paar Sitzungen ausgeschaltet — warum, steht im Verlauf. Wenn sie dir fehlen, antworte unten „ja, hätte sollen“.', 'Suite à tes réponses, j’ai désactivé les rappels pour quelques séances — tu trouveras pourquoi dans l’Historique. S’ils te manquent, réponds ci-dessous « oui, il aurait dû ».', 'Depois do seu feedback, desativei os avisos por algumas sessões — o motivo está no Histórico. Se sentir falta deles, responda “sim, devia” aqui embaixo.')
_tr7('kamae.paused_sub', '心拍は見ていますが、今は合図をオフにしています — 理由は「履歴」にあります。', '我在关注心率，但提示现在是关闭的——原因可以在“历史”里找到。', 'Слежу за пульсом, но подсказки сейчас выключены — почему, найдёшь в «Истории».', 'Vigilo tu pulso, pero ahora tengo los avisos desactivados — el porqué está en el Historial.', 'Ich beobachte deinen Puls, aber die Hinweise sind gerade ausgeschaltet — warum, steht im Verlauf.', 'Je surveille ton pouls, mais les rappels sont désactivés pour l’instant — tu trouveras pourquoi dans l’Historique.', 'Acompanho o seu pulso, mas os avisos estão desativados por enquanto — o motivo está no Histórico.')
_tr7('ob.step5.kicker', 'ステップ 5 / 5', '第 5 步，共 5 步', 'ШАГ 5 из 5', 'PASO 5 de 5', 'SCHRITT 5 von 5', 'ÉTAPE 5 sur 5', 'PASSO 5 de 5')
_tr7('ob.cue.title', 'ゲームで本当にイライラしたとき、アプリにどう知らせてほしいですか？', '当游戏把你惹得够呛时，你希望应用怎样提醒你？', 'Когда игра тебя как следует заведёт, как ты хочешь, чтобы приложение дало о себе знать?', 'Cuando el juego te saca de quicio, ¿cómo quieres que te avise la app?', 'Wenn dich ein Spiel richtig aufregt, wie soll sich die App melden?', 'Quand un jeu te met vraiment à cran, comment veux-tu que l’app se manifeste ?', 'Quando o jogo te tirar mesmo do sério, como você quer que o app avise?')
_tr7('ob.cue.voice', '音声でもかまわない', '用语音也可以', 'Можно и голосом', 'Con voz, sin problema', 'Gern auch mit Stimme', 'Avec la voix, ça me va', 'Pode ser com voz')
_tr7('ob.cue.sound', '効果音とビジュアルだけがいい', '最好只用音效和图片', 'Лучше только звук и картинка', 'Mejor solo sonido e imagen', 'Lieber nur Ton und Bild', 'Plutôt juste un son et une image', 'Prefiro só som e imagem')
_tr7('ob.cue.visual', 'ビジュアルだけ、何も言わないで', '只要图片，什么都别说', 'Только картинка, ничего не говори', 'Solo imagen, sin hablar', 'Nur ein Bild, sag nichts', 'Juste une image, ne dis rien', 'Só imagem, sem falar nada')
_tr7('ob.cue.unsure', 'わからない、アプリに任せる', '不确定，让应用自己摸索', 'Не знаю, пусть приложение разберётся само', 'No lo sé, que la app lo averigüe sola', 'Weiß nicht, die App soll es selbst herausfinden', 'Je ne sais pas, que l’app le découvre elle-même', 'Não sei, deixa o app descobrir por conta própria')
_tr7('ob.cue.note', 'これは「設定」の「サウンド」でいつでも変えられます。合図が邪魔だとアプリに伝えると、アプリは自分から控えめになります — ただし、ここで選んだより大きくなることはありません。', '随时可以在“设置”的“声音”部分更改。当你告诉应用提示碍事时，它也会自己变安静——但绝不会比你在这里选的更响。', 'Изменить это можно когда угодно в Настройках, в разделе «Звук». Если дашь приложению знать, что подсказки мешают, оно и само станет тише — но никогда не громче, чем выберешь здесь.', 'Puedes cambiarlo cuando quieras en Ajustes, en la sección Sonido. Si le dices a la app que los avisos molestan, se vuelve más discreta por sí sola — pero nunca más ruidosa de lo que elijas aquí.', 'Du kannst das jederzeit in den Einstellungen im Bereich Ton ändern. Wenn du der App sagst, dass die Hinweise stören, wird sie auch von selbst leiser — aber nie lauter als das, was du hier wählst.', 'Tu peux le changer à tout moment dans Paramètres, section Son. Quand tu fais savoir à l’app que les rappels te gênent, elle se fait plus discrète d’elle-même — mais jamais plus bruyante que ce que tu choisis ici.', 'Você pode mudar isso quando quiser em Configurações, na seção Som. Se você disser ao app que os avisos atrapalham, ele baixa o tom por conta própria — mas nunca passa do que você escolher aqui.')
_tr7('settings.cue_style', '合図の出し方', '我怎样出声', 'Как я даю о себе знать', 'Cómo aviso', 'Wie ich mich melde', 'Comment je me manifeste', 'Como eu aviso')
_tr7('settings.cue_style_sub', '合図が邪魔だと教えてくれたら、私は自分から控えめになります — ただし、ここで選んだより大きくなることはありません。仕事中はビジュアルだけで知らせます。', '当你告诉我提示碍事时，我也会自己变安静——但绝不会比你在这里选的更响。工作时我只用画面提示。', 'Если дашь мне знать, что подсказки мешают, я и сама стану тише — но никогда не громче, чем выберешь здесь. На работе я даю о себе знать только картинкой.', 'Si me dices que los avisos molestan, me vuelvo más discreta yo sola — pero nunca más ruidosa de lo que elijas aquí. En el trabajo solo aviso con imagen.', 'Wenn du mir sagst, dass die Hinweise stören, werde ich auch von selbst leiser — aber nie lauter als das, was du hier wählst. Bei der Arbeit melde ich mich nur mit Bild.', 'Quand tu me fais savoir que les rappels te gênent, je me fais plus discrète de moi-même — mais jamais plus bruyante que ce que tu choisis ici. Au travail, je ne me manifeste que par l’image.', 'Se você me disser que os avisos atrapalham, eu baixo o tom por conta própria — mas nunca passo do que você escolher aqui. No Trabalho, só aviso com imagem.')
_tr7('dnes.nonstop_input', 'もう {min} 分、入力の短い休みさえとらえられていません — 何かが休みなく入力を送っているのかもしれません。たとえばコントローラーのモーションセンサー（ジャイロ）や、デッドゾーンのないスティック。', '已经 {min} 分钟了，我连一次短暂的输入停顿都没捕捉到——可能有东西在不间断地报告输入，比如手柄的体感传感器（陀螺仪）或者没有死区的摇杆。', 'Уже {min} мин я не поймала ни одной короткой паузы во вводе — возможно, что-то сообщает о нём без перерыва, например датчик движения (гироскоп) геймпада или стик без мёртвой зоны.', 'Llevo {min} minutos sin detectar ni una pausa corta en la entrada — puede que algo la esté enviando sin parar, por ejemplo el sensor de movimiento del mando (giroscopio) o un stick sin zona muerta.', 'Seit {min} Minuten habe ich nicht einmal eine kurze Pause in der Eingabe erwischt — vielleicht sendet etwas ununterbrochen Eingaben, zum Beispiel der Bewegungssensor (Gyro) des Controllers oder ein Stick ohne Deadzone.', 'Depuis {min} minutes, je n’ai pas capté la moindre courte pause dans tes entrées — quelque chose les signale peut-être sans arrêt, par exemple le capteur de mouvement (gyro) de la manette ou un stick sans zone morte.', 'Há {min} minutos não detecto nem uma pausa curta na entrada — talvez algo esteja registrando entrada sem parar, como o sensor de movimento (giroscópio) do controle ou um analógico sem zona morta.')
_tr7('hr.trouble_pad', 'コントローラーでプレイしていますか？ 使っていないならジャイロ（モーションセンサー）をオフにして、スティックに小さなデッドゾーンを設定してください。そうしないとコントローラーが休みなく入力を送り続け、アプリは声をかけるための休みを見つけられません。', '用手柄玩？如果你不用陀螺仪（体感传感器），就把它关掉，并给摇杆设一个小死区。否则手柄可能会不间断地报告输入，应用就找不到可以出声的停顿。', 'Играешь с геймпадом? Выключи в нём гироскоп (датчик движения), если не пользуешься им, и дай стикам небольшую мёртвую зону. Иначе геймпад может сообщать о вводе без перерыва, и приложение не найдёт паузу, в которой могло бы подать голос.', '¿Juegas con mando? Desactívale el giroscopio (sensor de movimiento) si no lo usas, y dales a los sticks una pequeña zona muerta. Si no, el mando puede enviar entrada sin parar y la app no encuentra una pausa en la que avisar.', 'Spielst du mit Controller? Schalte das Gyro (Bewegungssensor) aus, wenn du es nicht nutzt, und gib den Sticks eine kleine Deadzone. Sonst kann der Controller ununterbrochen Eingaben senden, und die App findet keine Pause, in der sie sich melden könnte.', 'Tu joues à la manette ? Désactive son gyro (capteur de mouvement) si tu ne l’utilises pas, et donne aux sticks une petite zone morte. Sinon, la manette peut signaler des entrées sans arrêt, et l’app ne trouve pas de pause où se manifester.', 'Joga com controle? Desative o giroscópio (sensor de movimento) se não usa, e dê aos analógicos uma pequena zona morta. Senão o controle pode registrar entrada sem parar e o app não encontra uma pausa para avisar.')
_tr7('kamae.snoozed', '静かにしています', '静默中', 'Молчу', 'En silencio', 'Ich schweige', 'Je me tais', 'Em silêncio')
_tr7('kamae.snoozed_sub', '「今はいい」は {until} まで有効です — それまで声はかけませんが、心拍の計測は続けます。同じショートカットで早めに解除できます。', '“现在不要”持续到 {until}——在那之前我不会出声，但会继续测量心率。用同一个快捷键可以提前结束。', '«Не сейчас» действует до {until} — до тех пор я не подам голос, но пульс продолжаю измерять. Отменить раньше можно тем же сочетанием клавиш.', '«Ahora no» dura hasta las {until} — hasta entonces no aviso, pero sigo midiendo tu pulso. Puedes cancelarlo antes con el mismo atajo.', '„Jetzt nicht“ gilt bis {until} — bis dahin melde ich mich nicht, den Puls messe ich aber weiter. Früher beendest du es mit demselben Tastenkürzel.', '« Pas maintenant » vaut jusqu’à {until} — d’ici là, je ne me manifeste pas, mais je continue à mesurer ton pouls. Tu l’annules plus tôt avec le même raccourci.', 'O “agora não” vale até {until} — até lá não aviso, mas continuo medindo o seu pulso. Para cancelar antes, use o mesmo atalho.')
_tr7('settings.preview_sub_sound', '最初のリマインダーの音をゲーム中と同じように鳴らし、そのビジュアルを表示します。言葉はなし — 「合図の出し方」でそう選んだからです。', '按游戏中的效果播放第一条提醒的声音，并显示它的图片。不带语音——这是你在“我怎样出声”里选的。', 'Проигрывает звук первого напоминания так, как он прозвучит в игре, и показывает его картинку. Без слов — так ты выбрал в «Как я даю о себе знать».', 'Reproduce el sonido del primer recordatorio tal como sonará en el juego y muestra su imagen. Sin palabras — así lo elegiste en «Cómo aviso».', 'Spielt den Ton der ersten Erinnerung so ab, wie er im Spiel klingt, und zeigt ihr Bild. Ohne Worte — so hast du es unter „Wie ich mich melde“ gewählt.', 'Joue le son du premier rappel tel qu’il retentira en jeu, et montre son image. Sans paroles — c’est ce que tu as choisi dans « Comment je me manifeste ».', 'Toca o som do primeiro lembrete como ele vai soar no jogo e mostra a imagem dele. Sem palavras — foi o que você escolheu em “Como eu aviso”.')
_tr7('settings.preview_sub_visual', 'ビジュアルだけを選んだので、ゲーム中は何も鳴りません — 合図は表示されるだけです。このボタンは、最初のリマインダーのビジュアルを表示します。', '你只选了图片，所以游戏中不会有任何声音——提示只会显示出来。这个按钮会显示第一条提醒的图片。', 'Ты выбрал только картинку, так что в игре ничего не прозвучит — подсказка лишь покажется. Кнопка покажет картинку первого напоминания.', 'Elegiste solo imagen, así que en el juego no sonará nada — el aviso solo se mostrará. El botón muestra la imagen del primer recordatorio.', 'Du hast nur ein Bild gewählt, also erklingt im Spiel nichts — der Hinweis wird nur angezeigt. Der Knopf zeigt das Bild der ersten Erinnerung.', 'Tu as choisi seulement l’image, donc rien ne retentira en jeu — le rappel s’affiche seulement. Le bouton montre l’image du premier rappel.', 'Você escolheu só imagem, então nada toca no jogo — o aviso só aparece. O botão mostra a imagem do primeiro lembrete.')
_tr7('log.preview_no_picture', 'プレビュー：オンになっているリマインダーのどれも、ゲーム中のビジュアルがオンになっていません。このスタイルでは、ゲーム中にまったく合図を出せません。', '预览：没有任何已开启的提醒打开了游戏内图片，所以按这种方式，我在游戏中根本不会出现。', 'Предпросмотр: ни у одного включённого напоминания не включена картинка в игре, так что в этом стиле я бы в игре вообще не дала о себе знать.', 'Vista previa: ningún recordatorio activado tiene activada la imagen en el juego, así que con este estilo no avisaría en el juego en absoluto.', 'Vorschau: Bei keiner eingeschalteten Erinnerung ist das Bild im Spiel eingeschaltet, also würde ich mich in diesem Stil im Spiel gar nicht melden.', 'Aperçu : aucun rappel activé n’a son image en jeu activée, donc dans ce style je ne me manifesterais pas du tout en jeu.', 'Prévia: nenhum lembrete ativo tem a imagem no jogo ligada, então, neste estilo, eu não apareceria no jogo de jeito nenhum.')
_tr7('session.end.none_snoozed', 'このセッションのうち {min} 分は、あなたの「今はいい」が有効でした — その間は、望みどおり黙っていました。', '本次记录中有 {min} 分钟处于你的“现在不要”状态——那段时间我按你的意思保持了安静。', '{min} мин этой сессии действовало твоё «не сейчас» — тогда я молчала, как ты и хотел.', 'Durante {min} min de la sesión estuvo activo tu «ahora no» — entonces me quedé callada, como querías.', '{min} Min der Sitzung galt dein „Jetzt nicht“ — da habe ich geschwiegen, wie du es wolltest.', 'Pendant {min} min de la séance, ton « pas maintenant » était actif — je me suis tue alors, comme tu le voulais.', 'Por {min} min da sessão valeu o seu “agora não” — nesse tempo fiquei calada, como você quis.')
_tr7('tray.close_first', 'トレイ（時計の横のアイコン）で動き続けます。「時計から心拍を受け取る」がオンの間はポート {port} が電話のために開いたままになり、私が開始されている間（「今日」ページの ▶）は心拍の計測と保存を続けます。完全に終了するには、トレイアイコンを右クリック →「終了」。\n\nトレイで動かし続けますか？（いいえ = 今すぐ終了）', '我会继续在托盘里运行（时钟旁边的图标）。只要“接收手表的心率”开着，端口 {port} 就会为手机保持打开；只要我在运行（“今天”页面上的 ▶），我就会继续测量并保存心率。要彻底关闭我，右键点击托盘图标 → 退出。\n\n让我继续在托盘里运行吗？（否 = 立即退出）', 'Я продолжаю работать в трее (значок у часов). Пока включено «Слушать пульс с часов», порт {port} остаётся открытым для телефона, а пока я запущена (▶ на странице «Сегодня»), я продолжаю измерять и сохранять пульс. Полностью выключить меня можно правым кликом по значку в трее → «Выход».\n\nОставить меня работать в трее? (Нет = выйти сейчас)', 'Sigo funcionando en la bandeja (el icono junto a la hora). Mientras esté activado «Escuchar el pulso del reloj», el puerto {port} queda abierto para el móvil, y mientras esté iniciada (▶ en la página Hoy), sigo midiendo y guardando tu pulso. Para cerrarme del todo, haz clic derecho en el icono de la bandeja → Salir.\n\n¿Dejarme funcionando en la bandeja? (No = salir ahora)', 'Ich laufe in der Taskleiste weiter (Symbol neben der Uhrzeit). Solange „Puls von der Uhr empfangen“ eingeschaltet ist, bleibt Port {port} für das Handy offen, und solange ich gestartet bin (▶ auf der Seite Heute), messe und speichere ich den Puls weiter. Ganz beendest du mich mit einem Rechtsklick auf das Symbol in der Taskleiste → Beenden.\n\nSoll ich in der Taskleiste weiterlaufen? (Nein = sofort beenden)', 'Je continue de tourner dans la barre système (l’icône près de l’horloge). Tant que « Écouter le pouls de la montre » est activé, le port {port} reste ouvert pour le téléphone, et tant que je suis lancée (▶ sur la page Aujourd’hui), je continue de mesurer et d’enregistrer ton pouls. Pour me fermer complètement : clic droit sur l’icône de la barre système → Quitter.\n\nMe laisser tourner dans la barre système ? (Non = quitter tout de suite)', 'Continuo rodando na bandeja (o ícone ao lado do relógio da barra de tarefas). Enquanto “Ouvir o pulso do relógio” estiver ativado, a porta {port} fica aberta para o celular, e enquanto eu estiver ativa (▶ na página Hoje), continuo medindo e salvando o seu pulso. Para me fechar de vez, clique com o botão direito no ícone da bandeja → Sair.\n\nMe deixar rodando na bandeja? (Não = sair agora)')
_tr7('palette.placeholder', 'ページ、プロファイル、セリフの名前を入力…', '输入页面、配置文件或提示的名称…', 'Введи название страницы, профиля или подсказки…', 'Escribe el nombre de una página, un perfil o un aviso…', 'Tippe den Namen einer Seite, eines Profils oder eines Hinweises…', 'Tape le nom d’une page, d’un profil ou d’un rappel…', 'Digite o nome de uma página, perfil ou aviso…')
_tr7('palette.replay_intro', 'イントロをもう一度見る', '再看一次介绍', 'Показать вступление снова', 'Ver la introducción de nuevo', 'Intro erneut zeigen', 'Revoir l’intro', 'Mostrar a introdução de novo')
_tr7('palette.profile', 'プロファイル — {name}', '配置文件 — {name}', 'Профиль — {name}', 'Perfil — {name}', 'Profil — {name}', 'Profil — {name}', 'Perfil — {name}')
_tr7('palette.cat.help', 'ヘルプ', '帮助', 'Помощь', 'Ayuda', 'Hilfe', 'Aide', 'Ajuda')
_tr7('palette.cat.nav', 'ナビゲーション', '导航', 'Навигация', 'Navegación', 'Navigation', 'Navigation', 'Navegação')
_tr7('palette.cat.sound', 'サウンド', '声音', 'Звук', 'Sonido', 'Ton', 'Son', 'Som')
_tr7('palette.cat.app', 'アプリ', '应用', 'Приложение', 'App', 'App', 'App', 'App')
_tr7('palette.cat.profiles', 'プロファイル', '配置文件', 'Профили', 'Perfiles', 'Profile', 'Profils', 'Perfis')
_tr7('edge.after_game', '監視を止めたら、セリフを準備します。', '等你停止监听后，我再准备语音条目。', 'Подготовлю фразы, когда ты остановишь прослушивание.', 'Prepararé las frases cuando detengas la escucha.', 'Ich bereite die Sprachzeilen vor, wenn du das Zuhören stoppst.', 'Je préparerai les répliques quand tu arrêteras l’écoute.', 'Vou preparar as falas quando você parar a escuta.')
_tr7('ob.cue.online_note', '自然な音声はオンラインです：合図の文面（心拍は決して送りません）を、音声に変換するために Microsoft に送ります。Windows の音声は何も送りません — 「設定」→「サウンド」で切り替えられます。', '自然语音需要联网：提示的文字（绝不包括心率）会发送给 Microsoft 的服务转换成语音。Windows 语音不会发送任何东西——可以在“设置 → 声音”里切换。', 'Естественный голос работает онлайн: текст подсказок (но никогда не пульс) отправляется сервису Microsoft для преобразования в речь. Голос Windows ничего не отправляет — переключиться на него можно в «Настройки → Звук».', 'La voz natural funciona en línea: el texto de los avisos (nunca tu pulso) se envía al servicio de Microsoft para convertirlo en voz. La voz de Windows no envía nada — puedes cambiar a ella en Ajustes → Sonido.', 'Die natürliche Stimme ist online: Der Text der Hinweise (nie dein Puls) geht an Microsoft und wird dort in Sprache umgewandelt. Die Windows-Stimme schickt nichts — du wechselst zu ihr unter Einstellungen → Ton.', 'La voix naturelle passe par internet : le texte des rappels (jamais ton pouls) est envoyé au service Microsoft pour être converti en parole. La voix Windows n’envoie rien — tu peux la choisir dans Paramètres → Son.', 'A voz natural é online: o texto dos avisos (nunca o seu pulso) é enviado ao serviço da Microsoft para ser convertido em fala. A voz do Windows não envia nada — você pode trocar para ela em Configurações → Som.')
_tr7('settings.language_note', 'アプリはスロバキア語で書かれています。ほかの言語は AI の助けを借りた翻訳で、まだネイティブスピーカーの確認を受けていません — 間違いを見つけたら教えてください。', '本应用以斯洛伐克语编写。其他语言是借助 AI 翻译的，尚未经过母语者校对——如果你发现错误，请告诉我。', 'Приложение написано на словацком. Остальные языки — переводы с помощью ИИ, и носитель языка их ещё не проверял; если заметишь ошибку, дай знать.', 'La app está escrita en eslovaco. Los demás idiomas son traducciones hechas con ayuda de IA que todavía no ha revisado ningún hablante nativo — si ves un error, avísame.', 'Die App ist auf Slowakisch geschrieben. Die anderen Sprachen sind KI-gestützte Übersetzungen, die noch nicht von Muttersprachlern geprüft wurden — wenn du einen Fehler siehst, sag Bescheid.', 'L’app est écrite en slovaque. Les autres langues sont des traductions faites avec l’aide de l’IA, pas encore relues par un locuteur natif — si tu vois une erreur, dis-le-moi.', 'O app foi escrito em eslovaco. Os outros idiomas são traduções feitas com ajuda de IA e ainda não foram revisados por um falante nativo — se encontrar um erro, avise.')


# --- 0.2.1: "teraz nie" aj v ponuke ikony v liste --------------------------
# Ked skratku (Ctrl+Alt+Z) drzi ina appka, `RegisterHotKey` zlyha a hlasky
# sa dali stisit jedine zastavenim pocuvania - co zastavi aj meranie. Od
# 0.2.1 je "teraz nie" aj polozka v ponuke ikony v liste (`setup_tray`) a
# riadok v denniku pri zlyhani skratky hraca posle tam (`start_snooze_hotkey`).
# Veta o zlyhani slubuje len to, co plati vzdy ("pocuvanie to nezastavi"),
# nie meranie - stisenie sa da zapnut aj v zastavenej appke, a vtedy sa
# nemeria (rovnako ako `log.snooze_started`). SK/EN rucne, 7 jazykov hned
# pod nimi, cestina a bulharcina v `i18n_cs_bg.py`.
STRINGS.update({
    'tray.snooze': _sk_en('Teraz nie ({minutes} min)', 'Not now ({minutes} min)'),
    'log.hotkey_failed_tray': _sk_en(
        'Skratku {combo} drží iná aplikácia, takže nepôjde. „Teraz nie“ '
        'nájdeš aj v ponuke ikony v lište (pravý klik). Počúvanie to '
        'nezastaví.',
        'Another app holds {combo}, so the shortcut won’t work. “Not now” is '
        'also in the tray icon’s menu (right-click). It doesn’t stop '
        'listening.'),
})
_tr7('tray.snooze', '今はいい（{minutes} 分）', '现在不要（{minutes} 分钟）', 'Не сейчас ({minutes} мин)', 'Ahora no ({minutes} min)', 'Jetzt nicht ({minutes} Min.)', 'Pas maintenant ({minutes} min)', 'Agora não ({minutes} min)')
_tr7('log.hotkey_failed_tray', 'ショートカット {combo} は別のアプリが使っているため、使えません。「今はいい」はトレイアイコンのメニュー（右クリック）にもあります。監視は止まりません。', '快捷键 {combo} 被其他应用占用了，所以用不了。“现在不要”也在托盘图标的菜单里（右键）。这不会停止监听。', 'Сочетание {combo} занято другим приложением, так что оно не сработает. «Не сейчас» есть и в меню значка в трее (правый клик). Слушать при этом не перестаю.', 'Otra aplicación está usando el atajo {combo}, así que no funcionará. «Ahora no» también está en el menú del icono de la bandeja (clic derecho). La escucha sigue en marcha.', 'Das Tastenkürzel {combo} ist von einer anderen Anwendung belegt und funktioniert deshalb nicht. „Jetzt nicht“ gibt es auch im Menü des Symbols in der Taskleiste (Rechtsklick). Das Zuhören läuft trotzdem weiter.', 'Une autre application occupe le raccourci {combo}, il ne marchera donc pas. « Pas maintenant » se trouve aussi dans le menu de l’icône de la barre système (clic droit). Ça n’arrête pas l’écoute.', 'Outro aplicativo está usando o atalho {combo}, então ele não vai funcionar. “Agora não” também está no menu do ícone da bandeja (clique com o botão direito). Isso não para a escuta.')


# ==========================================================================
# CESTINA A BULHARCINA (0.2)
# ==========================================================================
#
# Preklad celej appky je v module `i18n_cs_bg.py` (dva slovniky kluc -> text),
# aby tento subor nenarastol o dalsie dva stlpce. Vklada sa az tu, po vsetkych
# `STRINGS.update` a `_tr7`, takze meni len cs a bg.
#
# Kluc bez ceskeho alebo bulharskeho prekladu (novy kluc, plny slovnik s
# deviatimi jazykmi) dostane anglictinu - rovnako ako `_sk_en` pri ostatnych
# jazykoch - a tests/test_i18n_cs_bg.py ho nahlasi, aby neostal anglicky
# potichu. PyInstaller modul zoberie cez tento import (a pre istotu aj cez
# hiddenimports v Dandurf.spec).
from i18n_cs_bg import BG as _BG, CS as _CS  # noqa: E402

for _kod, _preklady in ((LANG_CS, _CS), (LANG_BG, _BG)):
    for _k, _v in _preklady.items():
        if _k in STRINGS:
            STRINGS[_k][_kod] = _v
for _zaznam in STRINGS.values():
    for _kod in (LANG_CS, LANG_BG):
        if _kod not in _zaznam:
            _zaznam[_kod] = _zaznam.get(LANG_EN, _zaznam.get(LANG_SK, ""))
