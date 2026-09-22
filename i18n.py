"""Preklady rozhrania - Slovencina / Anglictina / Japoncina / Cinstina
(zjednodusena) / Rustina / Spanielcina / Nemcina / Francuzstina /
Portugalcina (Brazilia).

Sada jazykov = rozhranie appky (SK/EN/JA) + najpopularnejsie jazyky
hracov na Steame (Steam Hardware & Software Survey + Valve GDC'25 data).

Cele UI sa po prepnuti jazyka prekresli odznova (rovnaky princip ako pri
prepnuti vizualnej temy), takze staci menit `_lang["code"]` a znova
zavolat `tr()` pri stavbe widgetov - ziadny widget si preklad
nepamataeta trvalo.

POZNAMKA K PREKLADOM: zh/ru/es/de/fr/pt su preklady vytvorene pomocou AI
(Claude) - odporucame pred sirokym vydanim appky necha' ich prejst
rodenym hovoriacim, najma obsah v guide.* (biomechanika/dychove techniky),
kde presnost formulacie ma realny vyznam.
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
DEFAULT_LANG = LANG_SK
LANGUAGES = (LANG_SK, LANG_EN, LANG_JA, LANG_ZH, LANG_RU, LANG_ES, LANG_DE, LANG_FR, LANG_PT)

_lang = {"code": DEFAULT_LANG}


def set_lang(code):
    _lang["code"] = code if code in LANGUAGES else DEFAULT_LANG


def tr(msg_key, **kwargs):
    entry = STRINGS.get(msg_key)
    if entry is None:
        return msg_key
    text = entry.get(_lang["code"], entry.get(DEFAULT_LANG, msg_key))
    return text.format(**kwargs) if kwargs else text


# Zvlastna hodnota pre "jazyk v hre" - drz sa jazyka rozhrania.
LANG_SAME_AS_APP = "app"


def _win_locale():
    """Kod locale prihlaseneho uzivatela, napr. 'de-DE'. Prazdny = neznamy.

    Oddelene od `system_lang()` kvoli testom - toto je jediny kus, ktory
    sa pyta operacneho systemu, takze sa da v teste vymenit a zvysok
    mapovania overit na vsetkych devatich jazykoch.
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
    """Jazyk Windowsu prelozeny na jeden z nasich devatich.

    PRECO TO EXISTUJE: pri prvom spusteni sa appka nastavovala na
    SLOVENCINU - lebo tak ju pisal autor. Na Steame si ju ale kupi Nemec,
    Brazilcan alebo Japonec a prve, co uvidi, je jazyk, ktoremu nerozumie,
    a musi ho hladat v nastaveniach. Preto sa pri prvom starte berie jazyk
    systemu, a ked ho medzi nasimi devatimi nemame, anglictina - nie
    slovencina.

    Ulozena volba hraca ma vzdy prednost; toto sa pyta len vtedy, ked
    este ziadna nie je.
    """
    kod = _win_locale() or ""
    primarny = kod.replace("_", "-").lower().split("-")[0]
    if primarny in LANGUAGES:
        return primarny
    # Cestina medzi nasimi devatimi nie je, ale pre ceskeho hraca je
    # slovencina zrozumitelnejsia nez anglictina.
    if primarny == "cs":
        return LANG_SK
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
    text = entry.get(code if code in LANGUAGES else _lang["code"],
                     entry.get(DEFAULT_LANG, msg_key))
    return text.format(**kwargs) if kwargs else text


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
    'onboarding.badge': {
        'sk': '🌿 ZANSHIN DOJOSYNC',
        'en': '🌿 ZANSHIN DOJOSYNC',
        'ja': '🌿 ZANSHIN DOJOSYNC',
        'zh': '🌿 ZANSHIN DOJOSYNC',
        'ru': '🌿 ZANSHIN DOJOSYNC',
        'es': '🌿 ZANSHIN DOJOSYNC',
        'de': '🌿 ZANSHIN DOJOSYNC',
        'fr': '🌿 ZANSHIN DOJOSYNC',
        'pt': '🌿 ZANSHIN DOJOSYNC',
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
    'onboarding.zen.title': {
        'sk': '墨 Sumi — atrament',
        'en': '墨 Sumi — ink',
        'ja': '墨 Sumi — ink',
        'zh': '墨 Sumi — ink',
        'ru': '墨 Sumi — ink',
        'es': '墨 Sumi — ink',
        'de': '墨 Sumi — ink',
        'fr': '墨 Sumi — ink',
        'pt': '墨 Sumi — ink',
    },
    'onboarding.zen.desc': {
        'sk': 'Teplá atramentová čerň so zlatým akcentom.\nPre nočné hranie, keď modrá tlačí do očí.',
        'en': 'Warm ink black with a gold accent.\nFor night sessions when blue is too much.',
        'ja': 'Warm ink black with a gold accent.\nFor night sessions when blue is too much.',
        'zh': 'Warm ink black with a gold accent.\nFor night sessions when blue is too much.',
        'ru': 'Warm ink black with a gold accent.\nFor night sessions when blue is too much.',
        'es': 'Warm ink black with a gold accent.\nFor night sessions when blue is too much.',
        'de': 'Warm ink black with a gold accent.\nFor night sessions when blue is too much.',
        'fr': 'Warm ink black with a gold accent.\nFor night sessions when blue is too much.',
        'pt': 'Warm ink black with a gold accent.\nFor night sessions when blue is too much.',
    },
    'onboarding.modern.title': {
        'sk': '藍 Aizome — indigo',
        'en': '藍 Aizome — indigo',
        'ja': '藍 Aizome — indigo',
        'zh': '藍 Aizome — indigo',
        'ru': '藍 Aizome — indigo',
        'es': '藍 Aizome — indigo',
        'de': '藍 Aizome — indigo',
        'fr': '藍 Aizome — indigo',
        'pt': '藍 Aizome — indigo',
    },
    'onboarding.modern.desc': {
        'sk': 'Indigová modrá dōgi na atramentovej.\nPokoj bojového umenia, nie „tmavý režim“.',
        'en': 'Indigo dōgi blue over ink.\nMartial-arts calm, not a ”dark mode”.',
        'ja': 'Indigo dōgi blue over ink.\nMartial-arts calm, not a ”dark mode”.',
        'zh': 'Indigo dōgi blue over ink.\nMartial-arts calm, not a ”dark mode”.',
        'ru': 'Indigo dōgi blue over ink.\nMartial-arts calm, not a ”dark mode”.',
        'es': 'Indigo dōgi blue over ink.\nMartial-arts calm, not a ”dark mode”.',
        'de': 'Indigo dōgi blue over ink.\nMartial-arts calm, not a ”dark mode”.',
        'fr': 'Indigo dōgi blue over ink.\nMartial-arts calm, not a ”dark mode”.',
        'pt': 'Indigo dōgi blue over ink.\nMartial-arts calm, not a ”dark mode”.',
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
        'ja': '→ スロット3を有効化（ADS／右クリック：「Release」+ シンギングボウル）',
        'zh': '→ 启用插槽3（开镜／右键："放松" + 颂钵声）',
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
        'sk': '→ Aktivuje Slot 2 (Prebíjanie / R: „Teeth“ + drevený blok)',
        'en': '→ Enables Slot 2 (Reload / R: "Teeth" + wood temple block)',
        'ja': '→ スロット2を有効化（リロード／R：「Teeth」+ 木製テンプルブロック）',
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
        'ja': '→ スロット1を有効化（しゃがみ／C：「Grounded」+ 地鳴りの音）',
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
        'ja': '→ スロット4を有効化（呼吸／F：「Breathe」+ 息の音）',
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
    'settings.hr_critical_bpm_label': {
        'sk': 'Tep, pri ktorom pomôcť',
        'en': 'Heart rate to step in at',
        'ja': 'Heart rate to step in at',
        'zh': 'Heart rate to step in at',
        'ru': 'Heart rate to step in at',
        'es': 'Heart rate to step in at',
        'de': 'Heart rate to step in at',
        'fr': 'Heart rate to step in at',
        'pt': 'Heart rate to step in at',
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
        'ru': 'Часы подключились. Если пульс всё равно не приходит, выберите в приложении на часах сцену «Zanshin» и текстовый источник «Tep» — и проверьте, что часы действительно измеряют.',
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
        'ru': 'Порт {port} уже занят другой программой - чаще всего это вторая открытая копия Zanshin или запущенный OBS. Закройте её и снова включите мониторинг пульса.',
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
    'log.hr_breathing_triggered': {
        'sk': 'Tep {bpm} BPM prekročil kritickú hranicu na 5+ sekúnd — automaticky spúšťam dýchací kruh.',
        'en': 'Heart rate {bpm} BPM stayed above the critical threshold for 5+ seconds - auto-triggering the breathing circle.',
        'ja': '心拍数 {bpm} BPM が危険しきい値を5秒以上超えました - 呼吸の輪を自動的に起動します。',
        'zh': '心率 {bpm} BPM 持续超过临界值 5 秒以上 - 自动触发呼吸圆环。',
        'ru': 'Пульс {bpm} BPM превышал критический порог 5+ секунд - автоматически запускаю дыхательный круг.',
        'es': 'El ritmo cardíaco de {bpm} BPM superó el umbral crítico durante 5+ segundos - activando automáticamente el círculo de respiración.',
        'de': 'Herzfrequenz {bpm} BPM lag 5+ Sekunden über dem kritischen Schwellenwert - löse den Atemkreis automatisch aus.',
        'fr': 'Le rythme cardiaque de {bpm} BPM a dépassé le seuil critique pendant 5 s ou plus - déclenchement automatique du cercle de respiration.',
        'pt': 'A frequência cardíaca de {bpm} BPM ficou acima do limite crítico por 5+ segundos - acionando automaticamente o círculo de respiração.',
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
        'sk': 'Tep prekročil kritickú hranicu, ale dýchací kruh (Slot 4) máš vypnutý v „In-Game Vizuály“ — zapni si ho, nech ťa appka pri vysokom tepe vie upokojiť.',
        'en': 'Your heart rate crossed the critical threshold, but the breathing circle (Slot 4) is turned off in "In-Game Visuals" - enable it so the app can calm you down when your pulse spikes.',
        'ja': '心拍数が危険しきい値を超えましたが、呼吸の輪（スロット4）が「ゲーム内ビジュアル」でオフになっています - 心拍数が上がったときに落ち着けるよう、有効にしてください。',
        'zh': '心率已超过临界值，但呼吸圆环（插槽 4）在"游戏内视觉效果"中已关闭 - 请启用它，以便在心率飙升时帮助你平静下来。',
        'ru': 'Пульс превысил критический порог, но дыхательный круг (слот 4) отключён в «Внутриигровых визуалах» - включите его, чтобы приложение могло успокоить вас при высоком пульсе.',
        'es': 'Tu ritmo cardíaco superó el umbral crítico, pero el círculo de respiración (Slot 4) está desactivado en "Visuales en el juego" - actívalo para que la app pueda calmarte cuando se dispare el pulso.',
        'de': 'Deine Herzfrequenz hat den kritischen Schwellenwert überschritten, aber der Atemkreis (Slot 4) ist unter "In-Game-Visuals" ausgeschaltet - aktiviere ihn, damit dich die App bei hohem Puls beruhigen kann.',
        'fr': 'Ton rythme cardiaque a dépassé le seuil critique, mais le cercle de respiration (Slot 4) est désactivé dans « Visuels en jeu » - active-le pour que l\'application puisse t\'apaiser quand ton pouls s\'emballe.',
        'pt': 'Sua frequência cardíaca ultrapassou o limite crítico, mas o círculo de respiração (Slot 4) está desativado em "Visuais no jogo" - ative-o para que o app possa acalmá-lo quando o pulso disparar.',
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
    'log.safe_mode': {
        'sk': 'Anti-Cheat Safe Mode: vstupy sa len pasívne čítajú (žiadne blokovanie ani simulácia stlačení).',
        'en': 'Anti-Cheat Safe Mode: input is only read passively (no blocking, no simulated key/mouse presses).',
        'ja': 'アンチチート・セーフモード: 入力は受動的に読み取るだけです（ブロックやキー/マウス入力のシミュレーションは一切行いません）。',
        'zh': '反作弊安全模式：仅被动读取输入（不拦截、不模拟按键或鼠标点击）。',
        'ru': 'Безопасный режим против читов: ввод считывается только пассивно (без блокировки, без имитации нажатий клавиш/кнопок мыши).',
        'es': 'Modo seguro anti-trampas: la entrada solo se lee de forma pasiva (sin bloquear, sin simular pulsaciones de teclas/ratón).',
        'de': 'Anti-Cheat-Sicherheitsmodus: Eingaben werden nur passiv gelesen (keine Blockierung, keine simulierten Tasten-/Mausklicks).',
        'fr': 'Mode sûr anti-triche : les entrées ne sont lues que passivement (aucun blocage, aucune simulation de touches/clics souris).',
        'pt': 'Modo seguro anti-cheat: a entrada é lida apenas de forma passiva (sem bloqueio, sem simulação de teclas/cliques do mouse).',
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
    'slots.add': {
        'sk': '+ Pridať spúšťač',
        'en': '+ Add trigger',
        'ja': '+ トリガーを追加',
        'zh': '+ 添加触发器',
        'ru': '+ Добавить триггер',
        'es': '+ Añadir disparador',
        'de': '+ Trigger hinzufügen',
        'fr': '+ Ajouter un déclencheur',
        'pt': '+ Adicionar gatilho',
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
    'slot.new_text_default': {
        'sk': 'nová hláska',
        'en': 'new voice line',
        'ja': '新しいセリフ',
        'zh': '新语音条目',
        'ru': 'новая голосовая фраза',
        'es': 'nueva frase de voz',
        'de': 'neue Sprachzeile',
        'fr': 'nouvelle réplique vocale',
        'pt': 'nova fala de voz',
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
        'sk': 'Kedy sa appka ozve, riadi zaťaženie tela — nastavuje sa pre všetky hlášky naraz na stránke Spúšťače.',
        'en': 'When the app speaks is driven by your body load — set once for all cues on the Triggers page.',
        'ja': 'アプリが話すタイミングは身体の負荷で決まります。すべてのセリフに共通で「セリフ」ページで設定します。',
        'zh': '应用何时出声取决于身体负荷，在"提示语"页面为所有提示统一设置。',
        'ru': 'Когда приложение заговорит, решает нагрузка тела — задаётся сразу для всех реплик на странице «Реплики».',
        'es': 'Cuándo habla la app lo decide la carga corporal: se ajusta para todas las señales en la página Señales.',
        'de': 'Wann die App spricht, steuert die Körperbelastung — für alle Hinweise gemeinsam auf der Seite Hinweise.',
        'fr': "Le moment où l'app parle dépend de la charge corporelle — réglé pour toutes les phrases sur la page Phrases.",
        'pt': 'Quando o app fala depende da carga do corpo — definido para todas as falas na página Falas.',
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
        'pt': 'A tua própria voz (gravação)',
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
        'pt': 'Nenhuma — usa-se a voz (TTS).',
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
        'pt': 'De ficheiro',
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
        'pt': 'Se gravares a tua própria voz, toca em vez do TTS — inteira e limpa, sem o filtro de passos. Usada sempre que a voz soaria.',
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
        'pt': 'Ficheiro de áudio de voz para o slot {n}',
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
        'pt': 'Slot {n}: voz própria de ficheiro ({name})',
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
    'cue_rate.hint': {
        'sk': 'Jedna voľba namiesto štyroch čísel — prah, držanie, odstup a strop sa hýbu spolu, samostatne si protirečia.',
        'en': 'One choice instead of four numbers — threshold, hold, gap and cap move together; alone they contradict each other.',
        'ja': '4つの数値ではなく1つの選択で。しきい値・持続・間隔・上限は連動します（個別だと矛盾します）。',
        'zh': '用一个选择代替四个数值——阈值、持续、间隔与上限联动，单独调整会互相矛盾。',
        'ru': 'Один выбор вместо четырёх чисел — порог, удержание, интервал и лимит двигаются вместе; по отдельности они противоречат друг другу.',
        'es': 'Una opción en vez de cuatro números: umbral, mantenimiento, intervalo y tope se mueven juntos; por separado se contradicen.',
        'de': 'Eine Wahl statt vier Zahlen — Schwelle, Haltezeit, Abstand und Obergrenze bewegen sich zusammen; einzeln widersprechen sie sich.',
        'fr': 'Un choix au lieu de quatre nombres — seuil, maintien, écart et plafond bougent ensemble ; séparément ils se contredisent.',
        'pt': 'Uma escolha em vez de quatro números — limiar, permanência, intervalo e teto andam juntos; separados se contradizem.',
    },
    'cue_rate.menej': {
        'sk': 'Menej',
        'en': 'Less',
        'ja': '少なめ',
        'zh': '较少',
        'ru': 'Реже',
        'es': 'Menos',
        'de': 'Weniger',
        'fr': 'Moins',
        'pt': 'Menos',
    },
    'cue_rate.bezne': {
        'sk': 'Bežne',
        'en': 'Normal',
        'ja': '標準',
        'zh': '正常',
        'ru': 'Обычно',
        'es': 'Normal',
        'de': 'Normal',
        'fr': 'Normal',
        'pt': 'Normal',
    },
    'cue_rate.viac': {
        'sk': 'Viac',
        'en': 'More',
        'ja': '多め',
        'zh': '较多',
        'ru': 'Чаще',
        'es': 'Más',
        'de': 'Mehr',
        'fr': 'Plus',
        'pt': 'Mais',
    },
    'cue_rate.detail': {
        'sk': 'Ozvem sa, keď záťaž drží {hold} s nad {prah}. Najviac {strop}× za hodinu, odstup aspoň {odstup} min.',
        'en': 'I speak when load holds {hold} s above {prah}. At most {strop}× per hour, at least {odstup} min apart.',
        'ja': '負荷が{prah}を{hold}秒超え続けたら話します。1時間に最大{strop}回、間隔は{odstup}分以上。',
        'zh': '当负荷持续 {hold} 秒高于 {prah} 时出声。每小时最多 {strop} 次，间隔至少 {odstup} 分钟。',
        'ru': 'Подаю голос, когда нагрузка держится {hold} с выше {prah}. Не более {strop}× в час, интервал не менее {odstup} мин.',
        'es': 'Hablo cuando la carga se mantiene {hold} s por encima de {prah}. Máximo {strop}× por hora, con {odstup} min de separación.',
        'de': 'Ich melde mich, wenn die Belastung {hold} s über {prah} bleibt. Höchstens {strop}× pro Stunde, mindestens {odstup} min Abstand.',
        'fr': "Je parle quand la charge tient {hold} s au-dessus de {prah}. Au plus {strop}× par heure, {odstup} min d'écart minimum.",
        'pt': 'Falo quando a carga fica {hold} s acima de {prah}. No máximo {strop}× por hora, com pelo menos {odstup} min de intervalo.',
    },
    'cue_rate.next_session': {
        'sk': 'Zmena platí od ďalšej relácie — meniť prahy uprostred večera znamená merať pohyblivý cieľ.',
        'en': 'Takes effect next session — changing thresholds mid-evening means measuring a moving target.',
        'ja': '変更は次のセッションから有効です。途中で変えると測定対象が動いてしまいます。',
        'zh': '更改自下次会话生效——中途改动阈值等于测量一个移动的目标。',
        'ru': 'Изменение вступит в силу со следующей сессии — менять пороги посреди вечера значит мерить движущуюся цель.',
        'es': 'Se aplica en la próxima sesión: cambiar umbrales a media tarde es medir un objetivo en movimiento.',
        'de': 'Gilt ab der nächsten Sitzung — Schwellen mitten am Abend zu ändern heißt, ein bewegliches Ziel zu messen.',
        'fr': 'Prend effet à la prochaine session — changer les seuils en pleine soirée revient à mesurer une cible mobile.',
        'pt': 'Vale a partir da próxima sessão — mudar limiares no meio da noite é medir um alvo em movimento.',
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
        'pt': 'Frequência das falas: {volba}',
    },
    'log.vizualy_napravene': {
        'sk': 'Zapol som in-game vizuály — bez aspoň jedného sa appka nemá ako ozvať. Vypnúť ich vieš v Nastaveniach → Hodinky.',
        'en': 'I turned the in-game visuals on — without at least one the app cannot speak at all. You can turn them off in Settings → Watch.',
        'ja': 'ゲーム内ビジュアルをオンにしました。1つもないとアプリは何も伝えられません。設定→時計でオフにできます。',
        'zh': '已开启游戏内视觉提示——一个都没有的话应用无法出声。可在设置→手表中关闭。',
        'ru': 'Я включил внутриигровые визуалы — без хотя бы одного приложение не может подать голос. Выключить можно в Настройки → Часы.',
        'es': 'He activado los visuales en el juego: sin al menos uno la app no puede hablar. Puedes desactivarlos en Ajustes → Reloj.',
        'de': 'Ich habe die In-Game-Visuals eingeschaltet — ohne mindestens eines kann sich die App gar nicht melden. Ausschalten in Einstellungen → Uhr.',
        'fr': "J'ai activé les visuels en jeu — sans au moins un, l'app ne peut rien dire. Tu peux les désactiver dans Réglages → Montre.",
        'pt': 'Liguei os visuais no jogo — sem pelo menos um o app não consegue falar. Pode desligá-los em Definições → Relógio.',
    },
    'log.overlay_test_ukonceny': {
        'sk': 'Ukončil som test vizuálu — kým beží, pohlcuje kliky myšou nad hrou.',
        'en': 'I ended the visual test — while it runs it swallows mouse clicks over the game.',
        'ja': 'ビジュアルのテストを終了しました。実行中はゲーム上のクリックを奪います。',
        'zh': '已结束视觉测试——测试运行时会吞掉游戏上的鼠标点击。',
        'ru': 'Я завершил тест визуала — пока он идёт, он перехватывает клики мышью поверх игры.',
        'es': 'He terminado la prueba del visual: mientras corre, se traga los clics sobre el juego.',
        'de': 'Ich habe den Visual-Test beendet — solange er läuft, schluckt er Mausklicks über dem Spiel.',
        'fr': "J'ai arrêté le test du visuel — tant qu'il tourne, il avale les clics au-dessus du jeu.",
        'pt': 'Terminei o teste do visual — enquanto corre, engole os cliques sobre o jogo.',
    },
    'palette.slot': {
        'sk': 'Hláška — {label}',
        'en': 'Cue — {label}',
        'ja': 'セリフ — {label}',
        'zh': '提示语 — {label}',
        'ru': 'Реплика — {label}',
        'es': 'Señal — {label}',
        'de': 'Hinweis — {label}',
        'fr': 'Phrase — {label}',
        'pt': 'Fala — {label}',
    },
    'slots.unnamed': {
        'sk': 'Hláška {n}',
        'en': 'Cue {n}',
        'ja': 'セリフ {n}',
        'zh': '提示语 {n}',
        'ru': 'Реплика {n}',
        'es': 'Señal {n}',
        'de': 'Hinweis {n}',
        'fr': 'Phrase {n}',
        'pt': 'Fala {n}',
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
        'pt': 'A ouvir, mas sem pulso',
    },
    'kamae.no_watch_sub': {
        'sk': 'Bez hodiniek neviem, kedy ti záťaž stúpa — ozvať sa nemám ako. Spáruj ich v Nastaveniach → Hodinky.',
        'en': 'Without a watch I cannot tell when your load rises — I have no way to speak up. Pair it in Settings → Watch.',
        'ja': '時計がないと負荷の上昇がわからず、声をかけようがありません。設定→時計でペアリングしてください。',
        'zh': '没有手表，我无法知道你的负荷何时上升，也就无从出声。请在设置→手表中配对。',
        'ru': 'Без часов я не знаю, когда нагрузка растёт, — подать голос мне нечем. Свяжи их в Настройки → Часы.',
        'es': 'Sin reloj no sé cuándo sube tu carga: no tengo forma de hablar. Vincúlalo en Ajustes → Reloj.',
        'de': 'Ohne Uhr weiß ich nicht, wann deine Belastung steigt — ich kann mich nicht melden. Koppel sie in Einstellungen → Uhr.',
        'fr': "Sans montre, je ne sais pas quand ta charge monte — je n'ai aucun moyen de parler. Appaire-la dans Réglages → Montre.",
        'pt': 'Sem relógio não sei quando a tua carga sobe — não tenho como falar. Emparelha-o em Definições → Relógio.',
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
    'kamae.no_hr_sub': {
        'sk': 'Senzor počúva, ale z hodiniek zatiaľ nič nechodí. Skontroluj, či naozaj merajú a sú na tej istej Wi‑Fi.',
        'en': 'The sensor is listening, but nothing is coming from the watch yet. Check that it is really measuring and on the same Wi‑Fi.',
        'ja': 'The sensor is listening, but nothing is coming from the watch yet. Check that it is really measuring and on the same Wi‑Fi.',
        'zh': 'The sensor is listening, but nothing is coming from the watch yet. Check that it is really measuring and on the same Wi‑Fi.',
        'ru': 'The sensor is listening, but nothing is coming from the watch yet. Check that it is really measuring and on the same Wi‑Fi.',
        'es': 'The sensor is listening, but nothing is coming from the watch yet. Check that it is really measuring and on the same Wi‑Fi.',
        'de': 'The sensor is listening, but nothing is coming from the watch yet. Check that it is really measuring and on the same Wi‑Fi.',
        'fr': 'The sensor is listening, but nothing is coming from the watch yet. Check that it is really measuring and on the same Wi‑Fi.',
        'pt': 'The sensor is listening, but nothing is coming from the watch yet. Check that it is really measuring and on the same Wi‑Fi.',
    },
    'dev.min_gap_clamped': {
        'sk': 'Odstup som zdvihol na {s} s — nižšie by si dve hlášky zneplatnili meracie okná.',
        'en': 'I raised the gap to {s} s — below that two cues invalidate each other’s measurement windows.',
        'ja': '間隔を {s} 秒に引き上げました。これより短いと2つのセリフが互いの測定窓を無効にします。',
        'zh': '我把间隔提高到 {s} 秒——再短两条提示会互相作废测量窗口。',
        'ru': 'Я поднял интервал до {s} с — ниже две реплики обнуляют измерительные окна друг друга.',
        'es': 'He subido el intervalo a {s} s: por debajo, dos señales invalidan sus ventanas de medición.',
        'de': 'Ich habe den Abstand auf {s} s angehoben — darunter entwerten zwei Hinweise ihre Messfenster gegenseitig.',
        'fr': "J'ai remonté l'écart à {s} s — en dessous, deux phrases invalident mutuellement leurs fenêtres de mesure.",
        'pt': 'Subi o intervalo para {s} s — abaixo disso duas falas invalidam as janelas de medição uma da outra.',
    },
    'log.cue_skipped_all_off': {
        'sk': 'Chvíľa na hlášku prišla, ale všetky sú vypnuté — mlčím.',
        'en': 'The moment for a cue came, but all of them are off — staying silent.',
        'ja': 'セリフの頃合いでしたが、すべてオフなので黙っています。',
        'zh': '到了该出声的时候，但所有提示都已关闭——保持安静。',
        'ru': 'Момент для реплики настал, но все они выключены — молчу.',
        'es': 'Llegó el momento de una señal, pero están todas apagadas: me callo.',
        'de': 'Der Moment für einen Hinweis war da, aber alle sind aus — ich schweige.',
        'fr': "Le moment d'une phrase est venu, mais elles sont toutes désactivées — je me tais.",
        'pt': 'Chegou o momento de uma fala, mas estão todas desligadas — fico calado.',
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
        'pt': 'A porta {port} está ocupada por outro programa — a tentar de novo ({n}/{z}). Costuma ser uma segunda cópia do app.',
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
        'pt': 'Porta ocupada — a tentar de novo',
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
    'settings.hr_critical_computed': {
        'sk': 'Tvoja hranica vysokého tepu: {bpm} BPM — spočítané z {n} tvojich relácií. Nenastavuje sa, appka si ju upraví, ako ťa spozná.',
        'en': 'Your high heart-rate limit: {bpm} BPM — computed from {n} of your sessions. Not a setting; the app adjusts it as it gets to know you.',
        'ja': 'あなたの高心拍ラインは {bpm} BPM — {n} 件のセッションから算出。設定ではなく、アプリが学習して調整します。',
        'zh': '你的高心率界线：{bpm} BPM——由你的 {n} 次会话算出。这不是设置项，应用会随着了解你而调整。',
        'ru': 'Твоя граница высокого пульса: {bpm} BPM — посчитана по {n} твоим сессиям. Это не настройка, приложение подправит её, узнавая тебя.',
        'es': 'Tu límite de pulso alto: {bpm} BPM, calculado con {n} de tus sesiones. No es un ajuste: la app lo corrige según te va conociendo.',
        'de': 'Deine Grenze für hohen Puls: {bpm} BPM — aus {n} deiner Sitzungen berechnet. Keine Einstellung; die App passt sie an, während sie dich kennenlernt.',
        'fr': "Ta limite de pouls élevé : {bpm} BPM — calculée sur {n} de tes sessions. Ce n'est pas un réglage : l'app l'ajuste en apprenant à te connaître.",
        'pt': 'O teu limite de pulso alto: {bpm} BPM — calculado a partir de {n} das tuas sessões. Não é uma definição; o app ajusta-o à medida que te conhece.',
    },
    'settings.hr_critical_learning': {
        'sk': 'Zatiaľ počítam s {bpm} BPM. Vlastnú hranicu ti spočítam po ďalších {treba} reláciách — nemusíš nastavovať nič.',
        'en': 'Using {bpm} BPM for now. I will compute your own limit after {treba} more sessions — nothing to set.',
        'ja': '今は {bpm} BPM を使っています。あと {treba} 回のセッションであなた専用の値を算出します。設定は不要です。',
        'zh': '目前使用 {bpm} BPM。再过 {treba} 次会话就能算出属于你的界线——无需设置。',
        'ru': 'Пока считаю с {bpm} BPM. Твою собственную границу посчитаю ещё через {treba} сессии — настраивать ничего не нужно.',
        'es': 'De momento uso {bpm} BPM. Calcularé tu propio límite tras {treba} sesiones más; no hay nada que ajustar.',
        'de': 'Vorerst rechne ich mit {bpm} BPM. Deine eigene Grenze berechne ich nach {treba} weiteren Sitzungen — nichts einzustellen.',
        'fr': "Pour l'instant je compte avec {bpm} BPM. Je calculerai ta propre limite après {treba} sessions de plus — rien à régler.",
        'pt': 'Por agora uso {bpm} BPM. Calculo o teu limite depois de mais {treba} sessões — não há nada para definir.',
    },
    'cue_rate.computed': {
        'sk': 'Ozvem sa, keď tvoja záťaž drží {hold} s nad {prah} — tú hranicu som si spočítal z {n} tvojich relácií ako úroveň, nad ktorou tráviš pätinu hrania. Najviac {strop}× za hodinu, odstup aspoň {odstup} min.',
        'en': 'I speak when your load holds {hold} s above {prah} — I computed that line from {n} of your sessions as the level you spend a fifth of your playtime above. At most {strop}× per hour, at least {odstup} min apart.',
        'ja': '負荷が {prah} を {hold} 秒超え続けたら話します。この線はあなたの {n} 件のセッションから、プレイ時間の5分の1を上回る水準として算出しました。1時間に最大 {strop} 回、間隔は {odstup} 分以上。',
        'zh': '当你的负荷持续 {hold} 秒高于 {prah} 时我会出声——这条线由你的 {n} 次会话算出，是你约五分之一游戏时间所处的水平之上。每小时最多 {strop} 次，间隔至少 {odstup} 分钟。',
        'ru': 'Подам голос, когда нагрузка держится {hold} с выше {prah} — эту границу я посчитал по {n} твоим сессиям как уровень, выше которого ты проводишь пятую часть игры. Не более {strop}× в час, интервал не менее {odstup} мин.',
        'es': 'Hablo cuando tu carga se mantiene {hold} s por encima de {prah}: calculé ese límite con {n} de tus sesiones, como el nivel por encima del cual pasas una quinta parte del juego. Máximo {strop}× por hora, con {odstup} min de separación.',
        'de': 'Ich melde mich, wenn deine Belastung {hold} s über {prah} bleibt — diese Linie habe ich aus {n} deiner Sitzungen als das Niveau berechnet, über dem du ein Fünftel deiner Spielzeit verbringst. Höchstens {strop}× pro Stunde, mindestens {odstup} min Abstand.',
        'fr': "Je parle quand ta charge tient {hold} s au-dessus de {prah} — j'ai calculé cette limite sur {n} de tes sessions, comme le niveau au-dessus duquel tu passes un cinquième de ton temps de jeu. Au plus {strop}× par heure, {odstup} min d'écart minimum.",
        'pt': 'Falo quando a tua carga se mantém {hold} s acima de {prah} — calculei esse limite a partir de {n} das tuas sessões, como o nível acima do qual passas um quinto do tempo de jogo. No máximo {strop}× por hora, com pelo menos {odstup} min de intervalo.',
    },
    'cue_rate.learning': {
        'sk': 'Zatiaľ počítam s číslami pre priemerného hráča: ozvem sa, keď záťaž drží {hold} s nad {prah}. Vlastnú hranicu si spočítam z tvojich relácií — nemusíš nastavovať nič.',
        'en': 'For now I use average-player numbers: I speak when load holds {hold} s above {prah}. I will compute your own line from your sessions — nothing to set.',
        'ja': '今は平均的なプレイヤー向けの数値を使っています。負荷が {prah} を {hold} 秒超えたら話します。あなた専用の値はセッションから算出します。設定は不要です。',
        'zh': '目前使用面向普通玩家的数值：负荷持续 {hold} 秒高于 {prah} 时出声。我会从你的会话中算出属于你的界线——无需设置。',
        'ru': 'Пока использую числа для среднего игрока: подам голос, когда нагрузка держится {hold} с выше {prah}. Твою собственную границу посчитаю по твоим сессиям — настраивать ничего не нужно.',
        'es': 'De momento uso números de jugador medio: hablo cuando la carga se mantiene {hold} s por encima de {prah}. Calcularé tu propio límite con tus sesiones; no hay nada que ajustar.',
        'de': 'Vorerst nutze ich Werte für einen Durchschnittsspieler: Ich melde mich, wenn die Belastung {hold} s über {prah} bleibt. Deine eigene Linie berechne ich aus deinen Sitzungen — nichts einzustellen.',
        'fr': "Pour l'instant j'utilise des valeurs de joueur moyen : je parle quand la charge tient {hold} s au-dessus de {prah}. Je calculerai ta propre limite à partir de tes sessions — rien à régler.",
        'pt': 'Por agora uso números de jogador médio: falo quando a carga se mantém {hold} s acima de {prah}. Calculo o teu próprio limite a partir das tuas sessões — não há nada para definir.',
    },
    'session.end.trace_hint': {
        'sk': 'Tep za celý večer. Trojuholníky sú hlášky, tenký pruh nad pásmami ukazuje, kde si mal ruky na klávesnici — teda kde sa pravdepodobne hralo.',
        'en': 'Your heart rate for the whole evening. Triangles are cues; the thin band above the zones shows where your hands were on the keyboard — so probably where you were playing.',
        'ja': '一晩の心拍です。三角はセリフ、ゾーンの上の細い帯は手がキーボードにあった時間 — つまりおそらくプレイ中の時間です。',
        'zh': '整晚的心率。三角形是提示语，色带上方的细条表示你的手在键盘上的时间——也就是大概在游戏中的时间。',
        'ru': 'Пульс за весь вечер. Треугольники — реплики, тонкая полоса над зонами показывает, где руки были на клавиатуре, то есть где ты, скорее всего, играл.',
        'es': 'Tu pulso de toda la noche. Los triángulos son las señales; la banda fina sobre las zonas muestra dónde tenías las manos en el teclado, o sea dónde probablemente jugabas.',
        'de': 'Dein Puls für den ganzen Abend. Dreiecke sind Hinweise; das schmale Band über den Zonen zeigt, wo deine Hände auf der Tastatur waren — also wo du vermutlich gespielt hast.',
        'fr': 'Ton pouls pour toute la soirée. Les triangles sont les phrases ; la fine bande au-dessus des zones montre où tes mains étaient sur le clavier, donc probablement où tu jouais.',
        'pt': 'O teu pulso da noite toda. Os triângulos são as falas; a faixa fina acima das zonas mostra onde tinhas as mãos no teclado — ou seja, onde provavelmente jogavas.',
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
        'sk': "{app} pripravený. Stlač 'Štart odpočúvania'.",
        'en': "{app} ready. Click 'Start listening'.",
        'ja': '{app} の準備ができました。「聞き取り開始」を押してください。',
        'zh': '{app} 已就绪。点击「开始监听」。',
        'ru': '{app} готов. Нажми «Начать прослушивание».',
        'es': '{app} listo. Pulsa «Empezar a escuchar».',
        'de': '{app} bereit. Klicke auf „Zuhören starten“.',
        'fr': "{app} prêt. Clique sur « Démarrer l'écoute ».",
        'pt': '{app} pronto. Clique em "Começar a ouvir".',
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
    'log.slot_added': {
        'sk': 'Pridaná hláška {n}. Napíš, čo má povedať — kedy sa ozve, rozhoduje appka sama.',
        'en': 'Cue {n} added. Type what it should say — when it speaks is up to the app.',
        'ja': 'セリフ {n} を追加しました。何を言うかを入力してください。いつ話すかはアプリが決めます。',
        'zh': '已添加提示语 {n}。请输入它要说的内容——何时出声由应用决定。',
        'ru': 'Реплика {n} добавлена. Напиши, что она должна сказать — когда заговорить, решает приложение.',
        'es': 'Señal {n} añadida. Escribe qué debe decir: cuándo habla lo decide la app.',
        'de': 'Hinweis {n} hinzugefügt. Schreib, was er sagen soll — wann er spricht, entscheidet die App.',
        'fr': "Phrase {n} ajoutée. Écris ce qu'elle doit dire — quand elle parle, c'est l'app qui décide.",
        'pt': 'Fala {n} adicionada. Escreve o que deve dizer — quando fala decide o app.',
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
        'sk': '📖  Sprievodca / Veda za aplikáciou',
        'en': '📖  Guide / The science behind it',
        'ja': '📖  ガイド / このアプリの科学的根拠',
        'zh': '📖  指南 / 背后的科学原理',
        'ru': '📖  Руководство / Наука за этим',
        'es': '📖  Guía / La ciencia detrás',
        'de': '📖  Anleitung / Die Wissenschaft dahinter',
        'fr': '📖  Guide / La science derrière',
        'pt': '📖  Guia / A ciência por trás',
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
        'sk': 'Sprievodca · Veda za aplikáciou',
        'en': 'Guide · The science behind it',
        'ja': 'ガイド・このアプリの科学的根拠',
        'zh': '指南 · 背后的科学原理',
        'ru': 'Руководство · Наука за этим',
        'es': 'Guía · La ciencia detrás',
        'de': 'Anleitung · Die Wissenschaft dahinter',
        'fr': 'Guide · La science derrière',
        'pt': 'Guia · A ciência por trás',
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
    'guide.block.science': {
        'sk': 'Veda',
        'en': 'The science',
        'ja': '科学的根拠',
        'zh': '科学原理',
        'ru': 'Наука',
        'es': 'La ciencia',
        'de': 'Die Wissenschaft',
        'fr': 'La science',
        'pt': 'A ciência',
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
        'sk': 'Prečo funguje',
        'en': 'Why it works',
        'ja': '効果がある理由',
        'zh': '为什么有效',
        'ru': 'Почему это работает',
        'es': 'Por qué funciona',
        'de': 'Warum es funktioniert',
        'fr': 'Pourquoi ça marche',
        'pt': 'Por que funciona',
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
    'guide.grounding.physiology': {
        'sk': 'Vzpriamenie chrbtice a aktivácia hlbokého stabilizačného systému (core).',
        'en': 'Straightening the spine and activating the deep core stabilizing system.',
        'ja': '背骨をまっすぐにし、深部の体幹安定システム（コア）を働かせる。',
        'zh': '挺直脊柱，激活深层核心稳定系统。',
        'ru': 'Выпрямление позвоночника и активация глубокой системы стабилизации кора.',
        'es': 'Enderezar la columna y activar el sistema profundo de estabilización del core.',
        'de': 'Aufrichten der Wirbelsäule und Aktivierung des tiefen Core-Stabilisierungssystems.',
        'fr': 'Redresser la colonne vertébrale et activer le système profond de stabilisation du tronc.',
        'pt': 'Endireitar a coluna e ativar o sistema profundo de estabilização do core.',
    },
    'guide.grounding.science': {
        'sk': 'Pri strese človek inštinktívne padá do „turtle neck“ (predsunutá hlava k monitoru), čo obmedzuje prietok krvi do mozgu a aktivuje amygdalu (panika). Uvedomenie si sedacích kostí a kontaktu nôh so zemou znižuje posturálne napätie.',
        'en': 'Under stress people instinctively collapse into a "turtle neck" (head jutting toward the monitor), which restricts blood flow to the brain and activates the amygdala (panic). Feeling your sit bones and the contact of your feet with the floor lowers postural tension.',
        'ja': 'ストレス下では人は無意識に「タートルネック」姿勢（頭がモニターに突き出る）に陥り、脳への血流が制限されて扁桃体（パニック反応）が活性化します。座骨と足が床に触れている感覚を意識すると、姿勢の緊張が和らぎます。',
        'zh': '在压力下，人会本能地缩成"乌龟脖"（头部向显示器前倾），这会限制脑部供血并激活杏仁核（恐慌反应）。感受坐骨的着力点以及双脚与地面的接触，能降低体态紧张。',
        'ru': 'В стрессе люди инстинктивно сжимаются в «черепашью шею» (голова тянется к монитору), что ограничивает приток крови к мозгу и активирует миндалевидное тело (паника). Ощущение седалищных костей и контакта стоп с полом снижает постуральное напряжение.',
        'es': 'Bajo estrés, la gente colapsa instintivamente en «cuello de tortuga» (cabeza adelantada hacia el monitor), lo que restringe el flujo sanguíneo al cerebro y activa la amígdala (pánico). Sentir los isquiones y el contacto de los pies con el suelo reduce la tensión postural.',
        'de': 'Unter Stress kollabieren Menschen instinktiv in einen „Schildkrötenhals“ (Kopf zum Monitor vorgeschoben), was den Blutfluss zum Gehirn einschränkt und die Amygdala aktiviert (Panik). Die Sitzbeinhöcker und den Kontakt der Füße mit dem Boden zu spüren senkt die Haltungsspannung.',
        'fr': "Sous stress, les gens s'affaissent instinctivement en « cou de tortue » (tête projetée vers l'écran), ce qui restreint le flux sanguin vers le cerveau et active l'amygdale (panique). Sentir ses ischions et le contact des pieds avec le sol réduit la tension posturale.",
        'pt': 'Sob estresse, as pessoas instintivamente entram em colapso no "pescoço de tartaruga" (cabeça projetada em direção ao monitor), o que restringe o fluxo sanguíneo para o cérebro e ativa a amígdala (pânico). Sentir os ísquios e o contato dos pés com o chão reduz a tensão postural.',
    },
    'guide.grounding.instruction': {
        'sk': 'Keď sa appka ozve, nezosypeš sa dopredu – precíť, ako sa tvoje sedacie kosti zaboria do stoličky. Uvoľni spodnú časť brucha a nechaj ramená padnúť. Hlava hore, ťažisko dole.',
        'en': "When the app speaks up, don't fold forward - feel your sit bones sink into the chair. Release the lower belly and let your shoulders drop. Head up, center of gravity down.",
        'ja': 'キーを押すときは、ただ押すだけでなく - 座骨が椅子に沈み込む感覚を感じてください。下腹部の力を抜き、肩を落とします。頭は上に、重心は下に。',
        'zh': '按键时不要只是按下去 - 感受坐骨沉入椅子。放松下腹部，让肩膀自然下沉。头向上，重心向下。',
        'ru': 'Когда нажимаешь клавишу, не просто нажимай её - почувствуй, как седалищные кости опускаются в кресло. Отпусти низ живота и дай плечам опуститься. Голова вверх, центр тяжести вниз.',
        'es': 'Cuando presiones la tecla, no la presiones sin más - siente cómo tus isquiones se hunden en la silla. Suelta el bajo vientre y deja caer los hombros. Cabeza arriba, centro de gravedad abajo.',
        'de': 'Wenn du die Taste drückst, drücke sie nicht einfach nur - spüre, wie deine Sitzbeinhöcker in den Stuhl sinken. Löse den Unterbauch und lass die Schultern fallen. Kopf hoch, Schwerpunkt runter.',
        'fr': "Quand tu appuies sur la touche, ne te contente pas d'appuyer - sens tes ischions s'enfoncer dans le siège. Relâche le bas-ventre et laisse tomber les épaules. Tête haute, centre de gravité bas.",
        'pt': 'Quando você pressionar a tecla, não pressione simplesmente - sinta seus ísquios afundarem na cadeira. Solte o baixo-ventre e deixe os ombros caírem. Cabeça para cima, centro de gravidade para baixo.',
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
        'pt': 'Quando cerras o maxilar sem dares por isso',
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
        'sk': 'Zovretá čeľusť je primárny evolučný prejav stresovej reakcie typu „bojuj alebo uteč“. Zovretie zubov reflexívne sťahuje svaly krku, ramien a predlaktí, čo radikálne zhoršuje jemnú motoriku a mikro-aiming ruky.',
        'en': 'A clenched jaw is a primary evolutionary marker of the "fight or flight" stress response. Clenching your teeth reflexively tightens the muscles of the neck, shoulders and forearms, which drastically worsens fine motor control and hand micro-aim.',
        'ja': '食いしばった顎は「闘争・逃走反応」の主要な進化的サインです。歯を食いしばると、首・肩・前腕の筋肉が反射的に収縮し、細かい運動制御と手のマイクロエイムを著しく悪化させます。',
        'zh': '咬紧牙关是"战或逃"应激反应的主要进化标志。反射性地咬紧牙齿会同时收紧颈部、肩部与前臂的肌肉，这会严重削弱精细动作控制与手部微调瞄准的能力。',
        'ru': 'Стиснутая челюсть - первичный эволюционный маркер стрессовой реакции «бей или беги». Сжатие зубов рефлекторно напрягает мышцы шеи, плеч и предплечий, что резко ухудшает тонкую моторику и микроприцеливание руки.',
        'es': 'Una mandíbula apretada es un marcador evolutivo primario de la respuesta al estrés de «lucha o huida». Apretar los dientes tensa reflejamente los músculos del cuello, hombros y antebrazos, lo que empeora drásticamente la motricidad fina y la micropuntería de la mano.',
        'de': 'Ein zusammengebissener Kiefer ist ein primäres evolutionäres Merkmal der „Kampf-oder-Flucht“-Stressreaktion. Zähneknirschen spannt reflexartig die Muskeln von Nacken, Schultern und Unterarmen an, was die Feinmotorik und das Mikro-Zielen der Hand drastisch verschlechtert.',
        'fr': 'Une mâchoire serrée est un marqueur évolutif primaire de la réponse au stress « combat ou fuite ». Serrer les dents tend par réflexe les muscles du cou, des épaules et des avant-bras, ce qui dégrade drastiquement la motricité fine et la micro-visée de la main.',
        'pt': 'Uma mandíbula travada é um marcador evolutivo primário da resposta de estresse "luta ou fuga". Cerrar os dentes tensiona reflexamente os músculos do pescoço, ombros e antebraços, o que piora drasticamente a motricidade fina e a micromira da mão.',
    },
    'guide.jaw.instruction': {
        'sk': 'Počas animácie reloadu oddel zuby od seba na 2 milimetre a odlep jazyk od horného podnebia. Povoľ svaly okolo úst. Uvoľnená čeľusť = uvoľnené zápästie.',
        'en': 'During the reload animation, part your teeth by about 2 millimeters and lift your tongue off the roof of your mouth. Release the muscles around your mouth. A relaxed jaw means a relaxed wrist.',
        'ja': 'リロードのアニメーション中に、歯を2ミリほど離し、舌を上あごから離してください。口周りの筋肉を緩めます。顎の脱力 = 手首の脱力。',
        'zh': '在换弹动画期间，把牙齿分开约2毫米，把舌头从上颚抬开。放松嘴部周围的肌肉。下颌放松，手腕自然也会放松。',
        'ru': 'Во время анимации перезарядки разожми зубы примерно на 2 миллиметра и оторви язык от нёба. Расслабь мышцы вокруг рта. Расслабленная челюсть означает расслабленное запястье.',
        'es': 'Durante la animación de recarga, separa los dientes unos 2 milímetros y despega la lengua del paladar. Suelta los músculos alrededor de la boca. Una mandíbula relajada significa una muñeca relajada.',
        'de': 'Öffne während der Nachlade-Animation die Zähne um etwa 2 Millimeter und löse die Zunge vom Gaumen. Löse die Muskeln rund um den Mund. Ein entspannter Kiefer bedeutet ein entspanntes Handgelenk.',
        'fr': "Pendant l'animation de rechargement, écarte les dents d'environ 2 millimètres et décolle la langue du palais. Relâche les muscles autour de la bouche. Une mâchoire détendue signifie un poignet détendu.",
        'pt': 'Durante a animação de recarga, separe os dentes cerca de 2 milímetros e afaste a língua do céu da boca. Solte os músculos ao redor da boca. Uma mandíbula relaxada significa um pulso relaxado.',
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
        'sk': 'Sympatický vs. parasympatický zrak (foveálne vs. periférne videnie).',
        'en': 'Sympathetic vs. parasympathetic vision (foveal vs. peripheral sight).',
        'ja': '交感神経系の視覚 vs 副交感神経系の視覚（中心視 vs 周辺視）。',
        'zh': '交感神经与副交感神经视觉模式（中央视觉 vs 周边视觉）。',
        'ru': 'Симпатическое vs парасимпатическое зрение (фовеальное vs периферийное).',
        'es': 'Visión simpática vs. parasimpática (visión foveal vs. periférica).',
        'de': 'Sympathisches vs. parasympathisches Sehen (foveales vs. peripheres Sehen).',
        'fr': 'Vision sympathique vs parasympathique (vision fovéale vs périphérique).',
        'pt': 'Visão simpática vs. parassimpática (visão foveal vs. periférica).',
    },
    'guide.periphery.science': {
        'sk': 'Tunelové videnie pri mierení prepína mozog do úzkeho foveálneho režimu, čo vyvoláva adrenalínový špic a kŕč v prstoch. Zjemnenie zraku (soft focus) zapája parasympatikus, udržuje rýchly reakčný čas na okraje obrazovky a bráni prepísaniu svalovej pamäte strachom zo zlyhania.',
        'en': 'Tunnel vision while aiming switches the brain into a narrow foveal mode, triggering an adrenaline spike and finger tension. Softening your focus engages the parasympathetic system, keeps reaction time fast at the edges of the screen, and stops fear of failure from overwriting muscle memory.',
        'ja': 'エイム中のトンネルビジョンは脳を狭い中心視モードに切り替え、アドレナリンの急上昇と指のこわばりを引き起こします。視線を柔らかくする（ソフトフォーカス）ことで副交感神経が働き、画面端への反応速度を保ちつつ、失敗への恐怖が筋肉記憶を上書きするのを防ぎます。',
        'zh': '瞄准时的隧道视野会让大脑切换到狭窄的中央视觉模式，引发肾上腺素飙升与手指紧绷。放柔焦点能激活副交感神经系统，让屏幕边缘的反应速度保持敏捷，并防止对失败的恐惧覆盖肌肉记忆。',
        'ru': 'Туннельное зрение при прицеливании переключает мозг в узкий фовеальный режим, вызывая всплеск адреналина и напряжение пальцев. Смягчение фокуса задействует парасимпатическую систему, сохраняет быстроту реакции на краях экрана и не даёт страху неудачи перезаписать мышечную память.',
        'es': 'La visión de túnel al apuntar cambia el cerebro a un modo foveal estrecho, provocando un pico de adrenalina y tensión en los dedos. Suavizar el enfoque activa el sistema parasimpático, mantiene rápido el tiempo de reacción en los bordes de la pantalla y evita que el miedo al fallo sobrescriba la memoria muscular.',
        'de': 'Tunnelblick beim Zielen schaltet das Gehirn in einen engen fovealen Modus, was einen Adrenalinschub und Fingerspannung auslöst. Ein weicherer Fokus aktiviert das parasympathische System, hält die Reaktionszeit an den Bildschirmrändern schnell und verhindert, dass Versagensangst das Muskelgedächtnis überschreibt.',
        'fr': "La vision en tunnel en visant fait basculer le cerveau dans un mode fovéal étroit, provoquant un pic d'adrénaline et une tension des doigts. Adoucir le focus active le système parasympathique, garde un temps de réaction rapide sur les bords de l'écran et empêche la peur de l'échec d'écraser la mémoire musculaire.",
        'pt': 'A visão em túnel ao mirar muda o cérebro para um modo foveal estreito, disparando um pico de adrenalina e tensão nos dedos. Suavizar o foco aciona o sistema parassimpático, mantém o tempo de reação rápido nas bordas da tela e evita que o medo de errar sobrescreva a memória muscular.',
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
        'pt': 'Quando te esqueces de expirar',
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
        'sk': 'Najrýchlejší biologický mechanizmus na zrazenie srdcového tepu a vyrovnanie pomeru CO₂ v alveolách pľúc. Robí sa po prehratom súboji alebo počas killcamu.',
        'en': 'The fastest biological mechanism for lowering heart rate and rebalancing CO₂ in the lung alveoli. Do it after a lost fight or during a killcam.',
        'ja': '心拍数を下げ、肺胞内のCO₂バランスを整える、最も速い生体メカニズムです。負けた戦闘の後やキルカム中に行いましょう。',
        'zh': '这是降低心率并重新平衡肺泡内二氧化碳最快的生物机制。在输掉一场战斗后或观看击杀回放时使用。',
        'ru': 'Самый быстрый биологический механизм для снижения частоты сердечных сокращений и восстановления баланса CO₂ в альвеолах лёгких. Используй после проигранного боя или во время килкама.',
        'es': 'El mecanismo biológico más rápido para bajar la frecuencia cardíaca y reequilibrar el CO₂ en los alvéolos pulmonares. Hazlo tras perder un combate o durante una killcam.',
        'de': 'Der schnellste biologische Mechanismus, um die Herzfrequenz zu senken und das CO₂ in den Lungenbläschen neu auszugleichen. Mach das nach einem verlorenen Kampf oder während einer Killcam.',
        'fr': 'Le mécanisme biologique le plus rapide pour faire baisser le rythme cardiaque et rééquilibrer le CO₂ dans les alvéoles pulmonaires. À faire après un combat perdu ou pendant un killcam.',
        'pt': 'O mecanismo biológico mais rápido para baixar a frequência cardíaca e reequilibrar o CO₂ nos alvéolos pulmonares. Faça isso depois de perder um confronto ou durante um killcam.',
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
        'sk': 'Navodzuje pokojnú kontrolu a stabilizuje parasympatikus pri dlhšom čakaní v lobby alebo medzi zápasmi.',
        'en': 'Induces calm control and stabilizes the parasympathetic system during longer waits in the lobby or between matches.',
        'ja': 'ロビーでの待機中や試合の合間に、冷静なコントロールを生み出し、副交感神経を安定させます。',
        'zh': '在大厅等待或对局之间的较长间隙里，能带来平静的控制感并稳定副交感神经系统。',
        'ru': 'Вызывает спокойный контроль и стабилизирует парасимпатическую систему во время долгого ожидания в лобби или между матчами.',
        'es': 'Induce control calmado y estabiliza el sistema parasimpático durante las esperas más largas en el lobby o entre partidas.',
        'de': 'Erzeugt ruhige Kontrolle und stabilisiert das parasympathische System bei längeren Wartezeiten in der Lobby oder zwischen Matches.',
        'fr': 'Induit un contrôle calme et stabilise le système parasympathique pendant les attentes plus longues dans le lobby ou entre les matchs.',
        'pt': 'Induz controle calmo e estabiliza o sistema parassimpático durante esperas mais longas no lobby ou entre partidas.',
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
        'sk': 'Filozofia & hranice nástroja',
        'en': "Philosophy & the tool's limits",
        'ja': '哲学と、この道具の限界',
        'zh': '哲学与工具的边界',
        'ru': 'Философия и границы этого инструмента',
        'es': 'Filosofía y los límites de la herramienta',
        'de': 'Philosophie & die Grenzen des Werkzeugs',
        'fr': "Philosophie et les limites de l'outil",
        'pt': 'Filosofia e os limites da ferramenta',
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
        'sk': 'Stará budhistická metafora hovorí: keď prekročíš rieku na plti, nenosíš si ju ďalej na chrbte po súši — necháš ju na brehu. Táto appka je presne taká plť. Problém by nastal vtedy, ak by si bez nej vôbec nevedel uvoľniť telo, alebo keby si čakal, že softvér medituje za teba. V súlade to je vtedy, keď ju vnímaš ako tréningové kolieska: po pár týždňoch si telo samo spomenie na výdych a uvoľnenú čeľusť už len pri stlačení klávesu — hlas aj zvuk potichu ustúpia do pozadia.',
        'en': "An old Buddhist metaphor: once you've crossed the river on a raft, you don't keep carrying it on your back down the road - you leave it on the bank. This app is exactly that raft. It would become a problem if you couldn't relax your body at all without it running, or if you expected the software to meditate for you. It's aligned when you treat it as training wheels: after a couple of weeks your body starts recalling the exhale and the loose jaw on its own, just from the key press - the voice and sound quietly fade into the background.",
        'ja': '古い仏教の比喩があります - 筏で川を渡ったら、その後も筏を背負って陸を歩き続けたりはせず、岸に置いていく、というものです。このアプリはまさにその筏です。アプリが動いていないと体を全く緩められない、あるいはソフトウェアが代わりに瞑想してくれると期待するようになれば、それは問題です。逆に、これを補助輪として捉えられているなら健全です - 数週間もすれば、キーを押すだけで体が自然と息を吐き、顎を緩めることを思い出すようになり、声や音は静かに背景へ退いていきます。',
        'zh': '一个古老的佛教比喻：乘木筏渡过河流之后，你不会把它继续背在身上走完剩下的路 - 你会把它留在岸边。这个应用正是这样一只木筏。如果你完全无法在没有它运行的情况下放松身体，或者你期望软件替你冥想，那就出问题了。当你把它当作训练轮来看待时，它就是恰当的：几周之后，你的身体会开始仅凭按键这一动作，就自行想起呼气与放松下颌 - 声音与语音会悄悄退居幕后。',
        'ru': 'Старая буддийская метафора: переправившись через реку на плоту, ты не тащишь его дальше на спине по дороге - ты оставляешь его на берегу. Это приложение - именно такой плот. Проблема возникла бы, если бы ты вообще не мог расслабить тело без его работы, или если бы ты ожидал, что программа медитирует за тебя. Всё в порядке, если ты воспринимаешь его как тренировочные колёса: через пару недель тело само начинает вспоминать выдох и расслабленную челюсть просто от нажатия клавиши - голос и звук тихо уходят на второй план.',
        'es': 'Una vieja metáfora budista: una vez que has cruzado el río en una balsa, no sigues cargándola a la espalda por el camino - la dejas en la orilla. Esta app es exactamente esa balsa. Sería un problema si no pudieras relajar el cuerpo en absoluto sin ella funcionando, o si esperaras que el software meditara por ti. Está bien alineado cuando la tratas como ruedines de entrenamiento: tras un par de semanas tu cuerpo empieza a recordar por sí solo la exhalación y la mandíbula suelta con solo pulsar la tecla - la voz y el sonido se desvanecen silenciosamente al fondo.',
        'de': 'Eine alte buddhistische Metapher: Hast du den Fluss auf einem Floß überquert, trägst du es nicht weiter auf dem Rücken die Straße entlang - du lässt es am Ufer zurück. Diese App ist genau so ein Floß. Es würde zum Problem, wenn du deinen Körper ohne sie überhaupt nicht entspannen könntest, oder wenn du erwarten würdest, dass die Software für dich meditiert. Es passt, wenn du sie als Stützräder betrachtest: Nach ein paar Wochen beginnt dein Körper, sich das Ausatmen und den lockeren Kiefer allein vom Tastendruck her selbst zu merken - Stimme und Ton treten still in den Hintergrund.',
        'fr': "Une vieille métaphore bouddhiste : une fois la rivière traversée sur un radeau, tu ne continues pas à le porter sur ton dos le long de la route - tu le laisses sur la berge. Cette appli est exactement ce radeau. Ce serait un problème si tu ne pouvais absolument pas détendre ton corps sans qu'elle tourne, ou si tu attendais que le logiciel médite à ta place. C'est aligné quand tu la traites comme des petites roues d'entraînement : après quelques semaines, ton corps commence à se rappeler tout seul de l'expiration et de la mâchoire relâchée, rien qu'à l'appui de la touche - la voix et le son s'effacent doucement en arrière-plan.",
        'pt': 'Uma velha metáfora budista: depois de atravessar o rio numa jangada, você não continua carregando-a nas costas pela estrada - você a deixa na margem. Este app é exatamente essa jangada. Seria um problema se você não conseguisse relaxar o corpo de jeito nenhum sem ele rodando, ou se esperasse que o software meditasse por você. Está alinhado quando você o trata como rodinhas de treino: depois de algumas semanas, seu corpo começa a lembrar sozinho da expiração e da mandíbula solta só de apertar a tecla - a voz e o som recuam silenciosamente para o segundo plano.',
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
        'sk': 'V japonskom kendžucu sa rozlišuje sacunintō — meč použitý len na drvenie súpera, dominanciu a ego — a kacuninken — meč, ktorým premáhaš vlastný strach a hnev. Ak niekto vezme uvoľnenie tela len ako „bio-hack na výhru“, skôr či neskôr narazí na strop: pri každej neférovej smrti nastúpi frustrácia, lebo hlava zostala toxická. Telo a emócie sú spojené nádoby — nedá sa byť fyziologicky uvoľnený a zároveň plný slepej zlosti. Aj keď niekto začne z čisto sebeckého dôvodu (chcem vyhrávať), samotná prax ho nenápadne núti skrotiť vlastné ego.',
        'en': 'In Japanese kenjutsu, a distinction is made between satsujinken - a sword used purely to crush an opponent, for dominance and ego - and katsujinken - a sword used to overcome your own fear and anger. If someone treats bodily release as a pure "win bio-hack," they\'ll sooner or later hit a ceiling: every unfair death still triggers frustration, because the mind stayed toxic. Body and emotion are connected vessels - you can\'t be physiologically relaxed and blindly furious at the same time. Even someone who starts for a purely selfish reason (I want to win) ends up quietly forced by the practice itself to tame their own ego.',
        'ja': '日本の剣術には「殺人剣（さつじんけん）」- 相手を叩き潰し、支配し、自我を満たすためだけの剣 - と「活人剣（かつじんけん）」- 自分自身の恐れや怒りを克服するための剣、という区別があります。もし誰かが体の弛緩を単なる「勝つためのバイオハック」として扱うなら、いずれ限界にぶつかります - 理不尽な死のたびにフラストレーションが湧き上がります、心が毒されたままだからです。体と感情はつながった器であり、生理的にリラックスしながら盲目的に激怒することはできません。たとえ「勝ちたいだけ」という利己的な理由から始めたとしても、実践そのものが静かにその人の自我を手なずけていきます。',
        'zh': '在日本剑术中，有"杀人剑"（satsujinken）与"活人剑"（katsujinken）之分——前者纯粹用来压制对手、满足支配欲与自我，后者则用来克服自己的恐惧与愤怒。如果有人把身体上的放松纯粹当作"必胜的生物黑客手段"，迟早会撞上天花板：每一次不公平的死亡依然会引发挫败感，因为心智仍然是毒性的。身体与情绪是相连的容器 - 你不可能一边生理上放松，一边又盲目地暴怒。即便有人一开始纯粹出于自私的理由（我想赢）而开始使用，练习本身最终也会不动声色地促使他驯服自己的自我。',
        'ru': 'В японском кэндзюцу различают сацудзинкэн - меч, используемый исключительно для подавления соперника, ради доминирования и эго - и кацунинкэн - меч, которым преодолевают собственный страх и гнев. Если кто-то воспринимает телесное расслабление лишь как «чистый био-хак для победы», рано или поздно он упрётся в потолок: каждая несправедливая смерть всё равно вызывает фрустрацию, потому что разум остался токсичным. Тело и эмоции - сообщающиеся сосуды: нельзя быть физиологически расслабленным и одновременно слепо яростным. Даже тот, кто начинает из чисто эгоистичных побуждений (я хочу побеждать), в итоге незаметно для себя оказывается вынужден самой практикой укротить собственное эго.',
        'es': 'En el kenjutsu japonés se distingue entre satsujinken - una espada usada puramente para aplastar al oponente, por dominación y ego - y katsujinken - una espada usada para superar tu propio miedo e ira. Si alguien trata la liberación corporal solo como un «bio-hack puro para ganar», tarde o temprano chocará con un techo: cada muerte injusta sigue provocando frustración, porque la mente sigue siendo tóxica. El cuerpo y la emoción son vasos comunicantes - no puedes estar fisiológicamente relajado y ciegamente furioso a la vez. Incluso alguien que empieza por una razón puramente egoísta (quiero ganar) acaba siendo obligado silenciosamente por la propia práctica a domar su propio ego.',
        'de': 'Im japanischen Kenjutsu unterscheidet man zwischen Satsujinken - einem Schwert, das rein zur Zerschlagung des Gegners, für Dominanz und Ego eingesetzt wird - und Katsujinken - einem Schwert, mit dem man die eigene Angst und Wut überwindet. Wenn jemand körperliches Loslassen nur als reinen „Sieg-Bio-Hack“ betrachtet, wird er früher oder später an eine Decke stoßen: Jeder unfaire Tod löst weiterhin Frustration aus, weil der Geist toxisch geblieben ist. Körper und Emotion sind kommunizierende Gefäße - man kann nicht gleichzeitig physiologisch entspannt und blind wütend sein. Selbst wer aus rein egoistischen Gründen beginnt (ich will gewinnen), wird am Ende von der Praxis selbst still dazu gebracht, das eigene Ego zu zähmen.',
        'fr': "Dans le kenjutsu japonais, on distingue le satsujinken - une épée utilisée uniquement pour écraser l'adversaire, par domination et par ego - et le katsujinken - une épée utilisée pour surmonter sa propre peur et sa propre colère. Si quelqu'un considère la libération corporelle uniquement comme un pur « bio-hack pour gagner », il finira tôt ou tard par se heurter à un plafond : chaque mort injuste continue de déclencher de la frustration, parce que l'esprit est resté toxique. Le corps et l'émotion sont des vases communicants - on ne peut pas être physiologiquement détendu et aveuglément furieux en même temps. Même celui qui commence pour une raison purement égoïste (je veux gagner) finit, sans s'en rendre compte, forcé par la pratique elle-même à dompter son propre ego.",
        'pt': 'No kenjutsu japonês, faz-se uma distinção entre satsujinken - uma espada usada puramente para esmagar o oponente, por dominação e ego - e katsujinken - uma espada usada para superar o próprio medo e raiva. Se alguém trata o alívio corporal apenas como um puro "bio-hack para vencer", mais cedo ou mais tarde vai bater num teto: toda morte injusta ainda dispara frustração, porque a mente permaneceu tóxica. Corpo e emoção são vasos comunicantes - não dá para estar fisiologicamente relaxado e cegamente furioso ao mesmo tempo. Mesmo alguém que começa por um motivo puramente egoísta (eu quero vencer) acaba sendo silenciosamente forçado pela própria prática a domar o próprio ego.',
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
    'guide.philosophy.source1': {
        'sk': 'IEEE — biofeedback pre riadené dýchanie pri strese',
        'en': 'IEEE - biofeedback for stress-paced breathing',
        'ja': 'IEEE - ストレス時の呼吸調整とバイオフィードバック',
        'zh': 'IEEE - 用于压力节奏呼吸的生物反馈技术',
        'ru': 'IEEE - биообратная связь для дыхания в темпе стресса',
        'es': 'IEEE - biofeedback para respiración ritmada por estrés',
        'de': 'IEEE - Biofeedback für stressgetaktete Atmung',
        'fr': 'IEEE - biofeedback pour une respiration cadencée par le stress',
        'pt': 'IEEE - biofeedback para respiração ritmada pelo estresse',
    },
    'guide.philosophy.source2': {
        'sk': 'ACM CHI 2025 — Breath of Life (biofeedback hra)',
        'en': 'ACM CHI 2025 - Breath of Life (a biofeedback game)',
        'ja': 'ACM CHI 2025 - Breath of Life（バイオフィードバック・ゲーム）',
        'zh': 'ACM CHI 2025 - Breath of Life（一款生物反馈游戏）',
        'ru': 'ACM CHI 2025 - Breath of Life (игра с биообратной связью)',
        'es': 'ACM CHI 2025 - Breath of Life (un juego de biofeedback)',
        'de': 'ACM CHI 2025 - Breath of Life (ein Biofeedback-Spiel)',
        'fr': 'ACM CHI 2025 - Breath of Life (un jeu de biofeedback)',
        'pt': 'ACM CHI 2025 - Breath of Life (um jogo de biofeedback)',
    },
    'guide.philosophy.source3': {
        'sk': 'GitHub — keyboardsounds (podobný mechanizmus, iný účel)',
        'en': 'GitHub - keyboardsounds (similar mechanism, different purpose)',
        'ja': 'GitHub - keyboardsounds（似た仕組み、異なる目的）',
        'zh': 'GitHub - keyboardsounds（机制类似，用途不同）',
        'ru': 'GitHub - keyboardsounds (похожий механизм, другая цель)',
        'es': 'GitHub - keyboardsounds (mecanismo similar, propósito distinto)',
        'de': 'GitHub - keyboardsounds (ähnlicher Mechanismus, anderer Zweck)',
        'fr': 'GitHub - keyboardsounds (mécanisme similaire, but différent)',
        'pt': 'GitHub - keyboardsounds (mecanismo semelhante, propósito diferente)',
    },
    'guide.philosophy.source4': {
        # povodne Performetric (nastroj zanikol) - teraz recenzovana studia
        'sk': 'PMC (2020) — fyziologické a kognitívne funkcie po relácii súťažného esportu (únava)',
        'en': 'PMC (2020) - physiological and cognitive functions after a session of competitive esports (fatigue)',
        'ja': 'PMC (2020) - physiological and cognitive functions after a session of competitive esports (fatigue)',
        'zh': 'PMC (2020) - physiological and cognitive functions after a session of competitive esports (fatigue)',
        'ru': 'PMC (2020) - physiological and cognitive functions after a session of competitive esports (fatigue)',
        'es': 'PMC (2020) - physiological and cognitive functions after a session of competitive esports (fatigue)',
        'de': 'PMC (2020) - physiological and cognitive functions after a session of competitive esports (fatigue)',
        'fr': 'PMC (2020) - physiological and cognitive functions after a session of competitive esports (fatigue)',
        'pt': 'PMC (2020) - physiological and cognitive functions after a session of competitive esports (fatigue)',
    },
    'guide.philosophy.source5': {
        'sk': 'Pedraza-Ramirez et al. 2020 — psychológia esportu (systematický prehľad)',
        'en': 'Pedraza-Ramirez et al. 2020 - esports psychology (systematic review)',
        'ja': 'Pedraza-Ramirez et al. 2020 - eスポーツ心理学（システマティックレビュー）',
        'zh': 'Pedraza-Ramirez et al. 2020 - 电子竞技心理学（系统综述）',
        'ru': 'Pedraza-Ramirez et al. 2020 - психология киберспорта (систематический обзор)',
        'es': 'Pedraza-Ramirez et al. 2020 - psicología de los esports (revisión sistemática)',
        'de': 'Pedraza-Ramirez et al. 2020 - Psychologie des E-Sports (systematische Übersicht)',
        'fr': "Pedraza-Ramirez et al. 2020 - psychologie de l'esport (revue systématique)",
        'pt': 'Pedraza-Ramirez et al. 2020 - psicologia dos esports (revisão sistemática)',
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
        'sk': 'Teeth',
        'en': 'Teeth',
        'ja': '脱力',
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
        'zh': '放松',
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
    'hud.zone.critical': {
        'sk': 'Kritická',
        'en': 'Critical',
        'ja': 'Critical',
        'zh': 'Critical',
        'ru': 'Critical',
        'es': 'Critical',
        'de': 'Critical',
        'fr': 'Critical',
        'pt': 'Critical',
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
        'sk': 'Hra beží v exkluzívnom fullscreene – Windows v ňom cudzie prekrytia nevykreslí. Prepni hru na „Bez okrajov / Borderless“, inak vizuály neuvidíš.',
        'en': 'The game is in exclusive fullscreen - Windows will not draw any overlay on top of it. Switch the game to “Borderless” or you will not see the visuals.',
        'ja': 'The game is in exclusive fullscreen - Windows will not draw any overlay on top of it. Switch the game to “Borderless” or you will not see the visuals.',
        'zh': 'The game is in exclusive fullscreen - Windows will not draw any overlay on top of it. Switch the game to “Borderless” or you will not see the visuals.',
        'ru': 'The game is in exclusive fullscreen - Windows will not draw any overlay on top of it. Switch the game to “Borderless” or you will not see the visuals.',
        'es': 'The game is in exclusive fullscreen - Windows will not draw any overlay on top of it. Switch the game to “Borderless” or you will not see the visuals.',
        'de': 'The game is in exclusive fullscreen - Windows will not draw any overlay on top of it. Switch the game to “Borderless” or you will not see the visuals.',
        'fr': 'The game is in exclusive fullscreen - Windows will not draw any overlay on top of it. Switch the game to “Borderless” or you will not see the visuals.',
        'pt': 'The game is in exclusive fullscreen - Windows will not draw any overlay on top of it. Switch the game to “Borderless” or you will not see the visuals.',
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
        # "alfa 0.1", nie "2.1": cislovanie 2.x bolo z casov, ked appka
        # mierila na Steam ako pokracovanie predchodcu. Na GitHub ide ako
        # to, cim naozaj je - prva verejna alfa.
        'sk': 'alfa 0.1',
        'en': 'alpha 0.1',
        'ja': 'alpha 0.1',
        'zh': 'alpha 0.1',
        'ru': 'alpha 0.1',
        'es': 'alpha 0.1',
        'de': 'alpha 0.1',
        'fr': 'alpha 0.1',
        'pt': 'alpha 0.1',
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
        'pt': 'Clica em ▶ à esquerda. Quando escuto, a barra respira; senão, para.',
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
        'pt': "O círculo fechou-se",
    },
    'session.zanshin.body': {
        'sk': "Telo si už samo pamätá pokoj. Skús ďalší zápas bez appky — bola ti len plťou cez rieku. Keď si na druhom brehu, netreba ju niesť ďalej; kráčaj po svojich. A keby si ju niekedy potreboval, breh je vždy tu.",
        'en': "Your body remembers calm on its own now. Try the next match without the app — it was only a raft across the river. Once you're on the far bank, you needn't carry it; walk on your own. And if you ever need it again, the shore is always here.",
        'ja': "からだはもう自分で落ち着きを思い出す。次の試合はアプリなしで試してみて — これは川を渡る筏にすぎなかった。向こう岸に着いたら、もう背負わなくていい。自分の足で歩こう。もしまた必要になっても、岸はいつでもここにある。",
        'zh': "你的身体如今能自己记起平静。下一场比赛试着不用这个应用吧——它只是渡河的木筏。到了对岸，就无需再背着它；靠自己走。若哪天又需要它，河岸永远在这里。",
        'ru': "Тело теперь само вспоминает покой. Попробуй следующий матч без приложения — оно было лишь плотом через реку. На другом берегу его не нужно нести дальше; иди сам. А если оно снова понадобится — берег всегда здесь.",
        'es': "Tu cuerpo ya recuerda la calma por sí solo. Prueba la próxima partida sin la app — solo fue una balsa para cruzar el río. En la otra orilla no hace falta cargarla; camina por tu cuenta. Y si alguna vez la necesitas, la orilla siempre estará aquí.",
        'de': "Dein Körper erinnert sich jetzt von selbst an die Ruhe. Versuch das nächste Match ohne die App — sie war nur ein Floß über den Fluss. Am anderen Ufer musst du es nicht weitertragen; geh auf eigenen Beinen. Und solltest du es je wieder brauchen — das Ufer ist immer hier.",
        'fr': "Ton corps se souvient maintenant du calme tout seul. Essaie le prochain match sans l'appli — elle n'était qu'un radeau pour traverser la rivière. Sur l'autre rive, inutile de la porter ; marche par toi-même. Et si tu en as encore besoin un jour, la berge est toujours là.",
        'pt': "O teu corpo já se lembra da calma sozinho. Tenta a próxima partida sem a app — foi apenas uma jangada para atravessar o rio. Na outra margem, não precisas de a carregar; caminha por ti. E se um dia precisares dela outra vez, a margem está sempre aqui.",
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
        'sk': 'Prečo vlastne Zanshin vznikol? Ako človek, ktorý trávi pri počítači veľkú časť dňa — streamujem a hrám — som si časom všimol vzorec. Pri hraní často skĺzneme do úplného „autopilota“. Buď sa zaberieme tak, že stratíme pojem o čase aj o vlastnom tele, alebo naopak chytíme zbytočný tilt a naštveme sa, keď sa nedarí.\n\nHľadal som spôsob, ako si udržať chladnú hlavu a ostať vo „flow“ aj uprostred akcie alebo v sweaty ranked zápasoch. Vtedy som narazil na pojem zanshin — v bojových umeniach označuje stav plného sústredenia, uvoľnenia a čistej hlavy pripravenej na čokoľvek.\n\nTúto appku som napísal z obyčajnej osobnej potreby. Chcel som nenápadného pomocníka na pozadí, ktorý ma nenechá vyhorieť, občas mi pripomenie zhlboka sa nadýchnuť a udrží ma pri zemi. Nie sú to žiadne komplikované ezoterické cvičenia — ide jednoducho o to, aby nás hry viac bavili, aby sme hrali lepšie a hlavne aby sme sa nenaštvali pre nič za nič.\n\nA teraz narovinu: nie som programátor ani grafik. Túto appku som napísal vibe codingom — teda spolu s AI, vetu po vete, a učil som sa za pochodu. To, čo som priniesol ja, je nápad a roky strávené pri počítači.\n\nStojím na pleciach obrov. Nič z toho, čo appka robí, som nevymyslel — dýchanie, sústredenie, uvoľnená čeľusť, výskum o tepe a strese aj nástroje, v ktorých je to napísané. Všetko to niekto spravil predo mnou a nechal to voľne dostupné. Preto je Zanshin zadarmo a otvorený pod licenciou GPLv3: ktokoľvek si môže kód pozrieť, upraviť ho a posunúť ďalej — len ho nesmie zavrieť. Kto ho posunie ďalej, musí s ním odovzdať aj zdrojový kód a tú istú licenciu. Zdedil som to takto a chcem to takto aj odovzdať.\n\nAk ti toto nastavenie sedí, alebo si len chceš zahrať a pokecať, zastav sa u nás:',
        'en': 'Why did Zanshin actually come to be? As someone who spends a huge chunk of the day at the PC, streaming and playing games, I noticed a pattern over time. We often slip into complete “autopilot” mode while gaming. We either get so absorbed that we completely lose track of time and our own bodies, or on the flip side, we catch unnecessary tilt and get frustrated when things go wrong.\n\nI was looking for a way to keep a cool head and stay in the “flow” even in the middle of intense action or sweaty ranked matches. That is when I came across the concept of zanshin — which in martial arts refers to a state of being fully focused, relaxed, and having a clear mind ready for anything.\n\nI coded this app out of a simple personal need. I wanted a subtle background helper that prevents me from burning out, reminds me to take a deep breath every now and then, and keeps me grounded. It is not about any complicated esoteric exercises; it is simply about enjoying our games more, performing better, and most importantly, not getting tilted over nothing.\n\nAnd straight up: I am not a programmer or an artist. I vibe coded this app — together with AI, line by line, learning as I went. What I brought to it is the idea and years spent at the PC.\n\nI am standing on the shoulders of giants. Nothing this app does was invented by me — the breathing, the focus, the unclenched jaw, the research on heart rate and stress, the tools it is written in. Someone did all of it before me and left it out in the open. That is why Zanshin is free and open under the GPLv3 licence: anyone can read the code, change it and pass it on — they just cannot close it up. Whoever passes it on has to hand over the source and the same licence with it. I inherited it this way and I want to hand it on the same way.\n\nIf you vibe with this mindset, or if you just want to play some games and hang out, definitely drop by our community:',
        'ja': 'Why did Zanshin actually come to be? As someone who spends a huge chunk of the day at the PC, streaming and playing games, I noticed a pattern over time. We often slip into complete “autopilot” mode while gaming. We either get so absorbed that we completely lose track of time and our own bodies, or on the flip side, we catch unnecessary tilt and get frustrated when things go wrong.\n\nI was looking for a way to keep a cool head and stay in the “flow” even in the middle of intense action or sweaty ranked matches. That is when I came across the concept of zanshin — which in martial arts refers to a state of being fully focused, relaxed, and having a clear mind ready for anything.\n\nI coded this app out of a simple personal need. I wanted a subtle background helper that prevents me from burning out, reminds me to take a deep breath every now and then, and keeps me grounded. It is not about any complicated esoteric exercises; it is simply about enjoying our games more, performing better, and most importantly, not getting tilted over nothing.\n\nAnd straight up: I am not a programmer or an artist. I vibe coded this app — together with AI, line by line, learning as I went. What I brought to it is the idea and years spent at the PC.\n\nI am standing on the shoulders of giants. Nothing this app does was invented by me — the breathing, the focus, the unclenched jaw, the research on heart rate and stress, the tools it is written in. Someone did all of it before me and left it out in the open. That is why Zanshin is free and open under the GPLv3 licence: anyone can read the code, change it and pass it on — they just cannot close it up. Whoever passes it on has to hand over the source and the same licence with it. I inherited it this way and I want to hand it on the same way.\n\nIf you vibe with this mindset, or if you just want to play some games and hang out, definitely drop by our community:',
        'zh': 'Why did Zanshin actually come to be? As someone who spends a huge chunk of the day at the PC, streaming and playing games, I noticed a pattern over time. We often slip into complete “autopilot” mode while gaming. We either get so absorbed that we completely lose track of time and our own bodies, or on the flip side, we catch unnecessary tilt and get frustrated when things go wrong.\n\nI was looking for a way to keep a cool head and stay in the “flow” even in the middle of intense action or sweaty ranked matches. That is when I came across the concept of zanshin — which in martial arts refers to a state of being fully focused, relaxed, and having a clear mind ready for anything.\n\nI coded this app out of a simple personal need. I wanted a subtle background helper that prevents me from burning out, reminds me to take a deep breath every now and then, and keeps me grounded. It is not about any complicated esoteric exercises; it is simply about enjoying our games more, performing better, and most importantly, not getting tilted over nothing.\n\nAnd straight up: I am not a programmer or an artist. I vibe coded this app — together with AI, line by line, learning as I went. What I brought to it is the idea and years spent at the PC.\n\nI am standing on the shoulders of giants. Nothing this app does was invented by me — the breathing, the focus, the unclenched jaw, the research on heart rate and stress, the tools it is written in. Someone did all of it before me and left it out in the open. That is why Zanshin is free and open under the GPLv3 licence: anyone can read the code, change it and pass it on — they just cannot close it up. Whoever passes it on has to hand over the source and the same licence with it. I inherited it this way and I want to hand it on the same way.\n\nIf you vibe with this mindset, or if you just want to play some games and hang out, definitely drop by our community:',
        'ru': 'Why did Zanshin actually come to be? As someone who spends a huge chunk of the day at the PC, streaming and playing games, I noticed a pattern over time. We often slip into complete “autopilot” mode while gaming. We either get so absorbed that we completely lose track of time and our own bodies, or on the flip side, we catch unnecessary tilt and get frustrated when things go wrong.\n\nI was looking for a way to keep a cool head and stay in the “flow” even in the middle of intense action or sweaty ranked matches. That is when I came across the concept of zanshin — which in martial arts refers to a state of being fully focused, relaxed, and having a clear mind ready for anything.\n\nI coded this app out of a simple personal need. I wanted a subtle background helper that prevents me from burning out, reminds me to take a deep breath every now and then, and keeps me grounded. It is not about any complicated esoteric exercises; it is simply about enjoying our games more, performing better, and most importantly, not getting tilted over nothing.\n\nAnd straight up: I am not a programmer or an artist. I vibe coded this app — together with AI, line by line, learning as I went. What I brought to it is the idea and years spent at the PC.\n\nI am standing on the shoulders of giants. Nothing this app does was invented by me — the breathing, the focus, the unclenched jaw, the research on heart rate and stress, the tools it is written in. Someone did all of it before me and left it out in the open. That is why Zanshin is free and open under the GPLv3 licence: anyone can read the code, change it and pass it on — they just cannot close it up. Whoever passes it on has to hand over the source and the same licence with it. I inherited it this way and I want to hand it on the same way.\n\nIf you vibe with this mindset, or if you just want to play some games and hang out, definitely drop by our community:',
        'es': 'Why did Zanshin actually come to be? As someone who spends a huge chunk of the day at the PC, streaming and playing games, I noticed a pattern over time. We often slip into complete “autopilot” mode while gaming. We either get so absorbed that we completely lose track of time and our own bodies, or on the flip side, we catch unnecessary tilt and get frustrated when things go wrong.\n\nI was looking for a way to keep a cool head and stay in the “flow” even in the middle of intense action or sweaty ranked matches. That is when I came across the concept of zanshin — which in martial arts refers to a state of being fully focused, relaxed, and having a clear mind ready for anything.\n\nI coded this app out of a simple personal need. I wanted a subtle background helper that prevents me from burning out, reminds me to take a deep breath every now and then, and keeps me grounded. It is not about any complicated esoteric exercises; it is simply about enjoying our games more, performing better, and most importantly, not getting tilted over nothing.\n\nAnd straight up: I am not a programmer or an artist. I vibe coded this app — together with AI, line by line, learning as I went. What I brought to it is the idea and years spent at the PC.\n\nI am standing on the shoulders of giants. Nothing this app does was invented by me — the breathing, the focus, the unclenched jaw, the research on heart rate and stress, the tools it is written in. Someone did all of it before me and left it out in the open. That is why Zanshin is free and open under the GPLv3 licence: anyone can read the code, change it and pass it on — they just cannot close it up. Whoever passes it on has to hand over the source and the same licence with it. I inherited it this way and I want to hand it on the same way.\n\nIf you vibe with this mindset, or if you just want to play some games and hang out, definitely drop by our community:',
        'de': 'Why did Zanshin actually come to be? As someone who spends a huge chunk of the day at the PC, streaming and playing games, I noticed a pattern over time. We often slip into complete “autopilot” mode while gaming. We either get so absorbed that we completely lose track of time and our own bodies, or on the flip side, we catch unnecessary tilt and get frustrated when things go wrong.\n\nI was looking for a way to keep a cool head and stay in the “flow” even in the middle of intense action or sweaty ranked matches. That is when I came across the concept of zanshin — which in martial arts refers to a state of being fully focused, relaxed, and having a clear mind ready for anything.\n\nI coded this app out of a simple personal need. I wanted a subtle background helper that prevents me from burning out, reminds me to take a deep breath every now and then, and keeps me grounded. It is not about any complicated esoteric exercises; it is simply about enjoying our games more, performing better, and most importantly, not getting tilted over nothing.\n\nAnd straight up: I am not a programmer or an artist. I vibe coded this app — together with AI, line by line, learning as I went. What I brought to it is the idea and years spent at the PC.\n\nI am standing on the shoulders of giants. Nothing this app does was invented by me — the breathing, the focus, the unclenched jaw, the research on heart rate and stress, the tools it is written in. Someone did all of it before me and left it out in the open. That is why Zanshin is free and open under the GPLv3 licence: anyone can read the code, change it and pass it on — they just cannot close it up. Whoever passes it on has to hand over the source and the same licence with it. I inherited it this way and I want to hand it on the same way.\n\nIf you vibe with this mindset, or if you just want to play some games and hang out, definitely drop by our community:',
        'fr': 'Why did Zanshin actually come to be? As someone who spends a huge chunk of the day at the PC, streaming and playing games, I noticed a pattern over time. We often slip into complete “autopilot” mode while gaming. We either get so absorbed that we completely lose track of time and our own bodies, or on the flip side, we catch unnecessary tilt and get frustrated when things go wrong.\n\nI was looking for a way to keep a cool head and stay in the “flow” even in the middle of intense action or sweaty ranked matches. That is when I came across the concept of zanshin — which in martial arts refers to a state of being fully focused, relaxed, and having a clear mind ready for anything.\n\nI coded this app out of a simple personal need. I wanted a subtle background helper that prevents me from burning out, reminds me to take a deep breath every now and then, and keeps me grounded. It is not about any complicated esoteric exercises; it is simply about enjoying our games more, performing better, and most importantly, not getting tilted over nothing.\n\nAnd straight up: I am not a programmer or an artist. I vibe coded this app — together with AI, line by line, learning as I went. What I brought to it is the idea and years spent at the PC.\n\nI am standing on the shoulders of giants. Nothing this app does was invented by me — the breathing, the focus, the unclenched jaw, the research on heart rate and stress, the tools it is written in. Someone did all of it before me and left it out in the open. That is why Zanshin is free and open under the GPLv3 licence: anyone can read the code, change it and pass it on — they just cannot close it up. Whoever passes it on has to hand over the source and the same licence with it. I inherited it this way and I want to hand it on the same way.\n\nIf you vibe with this mindset, or if you just want to play some games and hang out, definitely drop by our community:',
        'pt': 'Why did Zanshin actually come to be? As someone who spends a huge chunk of the day at the PC, streaming and playing games, I noticed a pattern over time. We often slip into complete “autopilot” mode while gaming. We either get so absorbed that we completely lose track of time and our own bodies, or on the flip side, we catch unnecessary tilt and get frustrated when things go wrong.\n\nI was looking for a way to keep a cool head and stay in the “flow” even in the middle of intense action or sweaty ranked matches. That is when I came across the concept of zanshin — which in martial arts refers to a state of being fully focused, relaxed, and having a clear mind ready for anything.\n\nI coded this app out of a simple personal need. I wanted a subtle background helper that prevents me from burning out, reminds me to take a deep breath every now and then, and keeps me grounded. It is not about any complicated esoteric exercises; it is simply about enjoying our games more, performing better, and most importantly, not getting tilted over nothing.\n\nAnd straight up: I am not a programmer or an artist. I vibe coded this app — together with AI, line by line, learning as I went. What I brought to it is the idea and years spent at the PC.\n\nI am standing on the shoulders of giants. Nothing this app does was invented by me — the breathing, the focus, the unclenched jaw, the research on heart rate and stress, the tools it is written in. Someone did all of it before me and left it out in the open. That is why Zanshin is free and open under the GPLv3 licence: anyone can read the code, change it and pass it on — they just cannot close it up. Whoever passes it on has to hand over the source and the same licence with it. I inherited it this way and I want to hand it on the same way.\n\nIf you vibe with this mindset, or if you just want to play some games and hang out, definitely drop by our community:',
    },
    'about.between_lines': {
        'sk': 'Pre toho, kto číta medzi riadkami:\n\nTáto appka nemeria stres. Meria medzeru — medzi tým, čo hovorí tvoj tep, a tým, čo naozaj cítiš. Číslo je povrch; ty si hĺbka.\n\nA keď sa naučíš počúvať tú medzeru v sebe, začneš ju počuť aj inde — v tom, čo ľudia píšu a čo myslia, čo si žiadajú a čo potrebujú.\n\nNič sa nestráca. Len sa to premieňa — aj pozornosť. Drž dlaň otvorenú.',
        'en': 'For the one who reads between the lines:\n\nThis app does not measure stress. It measures the gap — between what your heart rate says and what you truly feel. The number is the surface; you are the depth.\n\nAnd once you learn to hear that gap in yourself, you will start to hear it elsewhere too — in what people write and what they mean, in what they ask for and what they need.\n\nNothing is lost. It only transforms — attention too. Keep your palm open.',
    },
    'about.copyright': {
        'sk': '© 2026 Dandurfin · GNU GPLv3 · Zanshin {version}\nTento program je slobodný softvér a ide s ním aj jeho zdrojový kód. Používať, štúdovať, upravovať a šíriť ho smie ktokoľvek — pod tou istou licenciou. Bez záruky.',
        'en': '© 2026 Dandurfin · GNU GPLv3 · Zanshin {version}\nThis program is free software and its source code travels with it. Anyone may use, study, modify and share it — under the same licence. With no warranty.',
        'ja': '© 2026 Dandurfin · GNU GPLv3 · Zanshin {version}\nThis program is free software and its source code travels with it. Anyone may use, study, modify and share it — under the same licence. With no warranty.',
        'zh': '© 2026 Dandurfin · GNU GPLv3 · Zanshin {version}\nThis program is free software and its source code travels with it. Anyone may use, study, modify and share it — under the same licence. With no warranty.',
        'ru': '© 2026 Dandurfin · GNU GPLv3 · Zanshin {version}\nThis program is free software and its source code travels with it. Anyone may use, study, modify and share it — under the same licence. With no warranty.',
        'es': '© 2026 Dandurfin · GNU GPLv3 · Zanshin {version}\nThis program is free software and its source code travels with it. Anyone may use, study, modify and share it — under the same licence. With no warranty.',
        'de': '© 2026 Dandurfin · GNU GPLv3 · Zanshin {version}\nThis program is free software and its source code travels with it. Anyone may use, study, modify and share it — under the same licence. With no warranty.',
        'fr': '© 2026 Dandurfin · GNU GPLv3 · Zanshin {version}\nThis program is free software and its source code travels with it. Anyone may use, study, modify and share it — under the same licence. With no warranty.',
        'pt': '© 2026 Dandurfin · GNU GPLv3 · Zanshin {version}\nThis program is free software and its source code travels with it. Anyone may use, study, modify and share it — under the same licence. With no warranty.',
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
        'sk': 'Nesledujem nič. Spustíš ma tlačidlom vľavo alebo sa spustím '
              'sám pri štarte hry.',
        'en': 'Not watching anything. Start me with the button on the left, '
              'or I start myself when a game launches.',
        'ja': 'Not watching anything. Start me with the button on the left, '
              'or I start myself when a game launches.',
        'zh': 'Not watching anything. Start me with the button on the left, '
              'or I start myself when a game launches.',
        'ru': 'Not watching anything. Start me with the button on the left, '
              'or I start myself when a game launches.',
        'es': 'Not watching anything. Start me with the button on the left, '
              'or I start myself when a game launches.',
        'de': 'Not watching anything. Start me with the button on the left, '
              'or I start myself when a game launches.',
        'fr': 'Not watching anything. Start me with the button on the left, '
              'or I start myself when a game launches.',
        'pt': 'Not watching anything. Start me with the button on the left, '
              'or I start myself when a game launches.',
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
    # citat a boli by to len tri dalsie retazce na prekladanie do devatich
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
    'dnes.stat_triggers': {
        'sk': 'Dychový kruh sa spustil',
        'en': 'Breathing circle fired',
        'ja': 'Breathing circle fired',
        'zh': 'Breathing circle fired',
        'ru': 'Breathing circle fired',
        'es': 'Breathing circle fired',
        'de': 'Breathing circle fired',
        'fr': 'Breathing circle fired',
        'pt': 'Breathing circle fired',
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
    'settings.theme': {
        'sk': 'Farebná téma',
        'en': 'Colour theme',
        'ja': 'Colour theme',
        'zh': 'Colour theme',
        'ru': 'Colour theme',
        'es': 'Colour theme',
        'de': 'Colour theme',
        'fr': 'Colour theme',
        'pt': 'Colour theme',
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
        'sk': 'Krátke vysvetlenie ku každej pripomienke — čo sa v tele deje a prečo to funguje.',
        'en': 'A short note on each reminder - what happens in the body and why it works.',
        'ja': 'A short note on each reminder - what happens in the body and why it works.',
        'zh': 'A short note on each reminder - what happens in the body and why it works.',
        'ru': 'A short note on each reminder - what happens in the body and why it works.',
        'es': 'A short note on each reminder - what happens in the body and why it works.',
        'de': 'A short note on each reminder - what happens in the body and why it works.',
        'fr': 'A short note on each reminder - what happens in the body and why it works.',
        'pt': 'A short note on each reminder - what happens in the body and why it works.',
    },
    'safety.title': {
        'sk': 'Prečo je to bezpečné voči anti-cheatu',
        'en': 'Why this is safe with anti-cheat',
        'ja': 'Why this is safe with anti-cheat',
        'zh': 'Why this is safe with anti-cheat',
        'ru': 'Why this is safe with anti-cheat',
        'es': 'Why this is safe with anti-cheat',
        'de': 'Why this is safe with anti-cheat',
        'fr': 'Why this is safe with anti-cheat',
        'pt': 'Why this is safe with anti-cheat',
    },
    'safety.body': {
        'sk': 'Appka kreslí vlastné priehľadné okno a nič viac. Nevstupuje do procesu hry, nehookuje vykresľovanie, nečíta pamäť hry ani obsah obrazovky. Okno neberie klik ani zameranie a nie je v Alt+Tab. Zámerne sa neskrýva pred screenshotmi ani OBS — to robia podvodné prekrytia.',
        'en': 'The app draws its own transparent window and nothing more. It never enters the game process, never hooks rendering, never reads game memory or screen contents. The window takes no clicks or focus and stays out of Alt+Tab. It deliberately does not hide from screenshots or OBS - that is what cheating overlays do.',
        'ja': 'The app draws its own transparent window and nothing more. It never enters the game process, never hooks rendering, never reads game memory or screen contents. The window takes no clicks or focus and stays out of Alt+Tab. It deliberately does not hide from screenshots or OBS - that is what cheating overlays do.',
        'zh': 'The app draws its own transparent window and nothing more. It never enters the game process, never hooks rendering, never reads game memory or screen contents. The window takes no clicks or focus and stays out of Alt+Tab. It deliberately does not hide from screenshots or OBS - that is what cheating overlays do.',
        'ru': 'The app draws its own transparent window and nothing more. It never enters the game process, never hooks rendering, never reads game memory or screen contents. The window takes no clicks or focus and stays out of Alt+Tab. It deliberately does not hide from screenshots or OBS - that is what cheating overlays do.',
        'es': 'The app draws its own transparent window and nothing more. It never enters the game process, never hooks rendering, never reads game memory or screen contents. The window takes no clicks or focus and stays out of Alt+Tab. It deliberately does not hide from screenshots or OBS - that is what cheating overlays do.',
        'de': 'The app draws its own transparent window and nothing more. It never enters the game process, never hooks rendering, never reads game memory or screen contents. The window takes no clicks or focus and stays out of Alt+Tab. It deliberately does not hide from screenshots or OBS - that is what cheating overlays do.',
        'fr': 'The app draws its own transparent window and nothing more. It never enters the game process, never hooks rendering, never reads game memory or screen contents. The window takes no clicks or focus and stays out of Alt+Tab. It deliberately does not hide from screenshots or OBS - that is what cheating overlays do.',
        'pt': 'The app draws its own transparent window and nothing more. It never enters the game process, never hooks rendering, never reads game memory or screen contents. The window takes no clicks or focus and stays out of Alt+Tab. It deliberately does not hide from screenshots or OBS - that is what cheating overlays do.',
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
        'en': 'Open Command Prompt and type ipconfig — look for “IPv4 Address“ (usually 192.168.x.x). Phone and PC must be on the same Wi‑Fi.',
        'ja': 'Open Command Prompt and type ipconfig — look for “IPv4 Address“ (usually 192.168.x.x). Phone and PC must be on the same Wi‑Fi.',
        'zh': 'Open Command Prompt and type ipconfig — look for “IPv4 Address“ (usually 192.168.x.x). Phone and PC must be on the same Wi‑Fi.',
        'ru': 'Open Command Prompt and type ipconfig — look for “IPv4 Address“ (usually 192.168.x.x). Phone and PC must be on the same Wi‑Fi.',
        'es': 'Open Command Prompt and type ipconfig — look for “IPv4 Address“ (usually 192.168.x.x). Phone and PC must be on the same Wi‑Fi.',
        'de': 'Open Command Prompt and type ipconfig — look for “IPv4 Address“ (usually 192.168.x.x). Phone and PC must be on the same Wi‑Fi.',
        'fr': 'Open Command Prompt and type ipconfig — look for “IPv4 Address“ (usually 192.168.x.x). Phone and PC must be on the same Wi‑Fi.',
        'pt': 'Open Command Prompt and type ipconfig — look for “IPv4 Address“ (usually 192.168.x.x). Phone and PC must be on the same Wi‑Fi.',
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
        'sk': 'Veda za tým →',
        'en': 'The science →',
        'ja': 'The science →',
        'zh': 'The science →',
        'ru': 'The science →',
        'es': 'The science →',
        'de': 'The science →',
        'fr': 'The science →',
        'pt': 'The science →',
    },
})

# Text opisoval mechanizmus SPRED fazy 2 ("tep nad hranicou 5 sekund"),
# co uz neplati: appka si z hranice pocita ZATAZ a spusta sa, ked zataz
# drzi hore dost dlho. Zamerne bez konkretnych cisel - tie sa menia
# (Cast C, ovladac "ako casto sa ozvem") a text by zase zastaral.
STRINGS['settings.hr_critical_bpm_hint_new'] = {
    'sk': 'Z tejto hranice si appka počíta záťaž — čím nižšie ju dáš, tým skôr sa tvoj tep ráta ako vysoký. Ozve sa, keď záťaž vydrží hore dosť dlho, nie hneď pri prekročení.',
    'en': 'The app derives your load from this ceiling — the lower you set it, the sooner your pulse counts as high. It speaks up when the load stays high long enough, not the moment you cross it.',
    'ja': 'この上限からアプリが負荷を計算します。低くするほど心拍が早く「高い」とみなされます。越えた瞬間ではなく、負荷が十分に長く高いままのときに声をかけます。',
    'zh': '应用会根据这个上限计算负荷。设得越低，你的心率越早被算作偏高。它不会在刚越过时就出声，而是在负荷持续偏高足够久时才提醒。',
    'ru': 'Из этого потолка приложение считает нагрузку — чем ниже ты его поставишь, тем раньше пульс считается высоким. Оно отзовётся, когда нагрузка продержится высоко достаточно долго, а не сразу при переходе.',
    'es': 'La app calcula tu carga a partir de este techo: cuanto más bajo lo pongas, antes contará tu pulso como alto. Habla cuando la carga se mantiene alta el tiempo suficiente, no en cuanto lo cruzas.',
    'de': 'Aus dieser Obergrenze berechnet die App deine Belastung — je niedriger du sie setzt, desto früher gilt dein Puls als hoch. Sie meldet sich, wenn die Belastung lange genug oben bleibt, nicht schon beim Überschreiten.',
    'fr': 'L’app calcule ta charge à partir de ce plafond : plus tu le baisses, plus vite ton pouls compte comme élevé. Elle parle quand la charge reste haute assez longtemps, pas dès que tu le franchis.',
    'pt': 'A app calcula a tua carga a partir deste limite — quanto mais baixo o puseres, mais cedo o teu pulso conta como alto. Fala quando a carga se mantém alta tempo suficiente, não assim que o ultrapassas.',
}

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
        'en': 'Click “Test“ and the icon appears on screen — grab it with the mouse and drag it wherever you want. Click again to save the position.',
        'ja': 'Click “Test“ and the icon appears on screen — grab it with the mouse and drag it wherever you want. Click again to save the position.',
        'zh': 'Click “Test“ and the icon appears on screen — grab it with the mouse and drag it wherever you want. Click again to save the position.',
        'ru': 'Click “Test“ and the icon appears on screen — grab it with the mouse and drag it wherever you want. Click again to save the position.',
        'es': 'Click “Test“ and the icon appears on screen — grab it with the mouse and drag it wherever you want. Click again to save the position.',
        'de': 'Click “Test“ and the icon appears on screen — grab it with the mouse and drag it wherever you want. Click again to save the position.',
        'fr': 'Click “Test“ and the icon appears on screen — grab it with the mouse and drag it wherever you want. Click again to save the position.',
        'pt': 'Click “Test“ and the icon appears on screen — grab it with the mouse and drag it wherever you want. Click again to save the position.',
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
    'colorpick.eyedropper': {
        'sk': 'Pipetka z obrazovky', 'en': 'Pick from screen',
        'ja': '画面から選択', 'zh': '从屏幕取色', 'ru': 'Взять с экрана',
        'es': 'Tomar de la pantalla', 'de': 'Vom Bildschirm wählen',
        'fr': "Prélever à l'écran", 'pt': 'Escolher do ecrã',
    },
    'colorpick.reset_default': {
        'sk': 'Predvolená', 'en': 'Default', 'ja': '既定', 'zh': '默认',
        'ru': 'По умолчанию', 'es': 'Predeterminado', 'de': 'Standard',
        'fr': 'Par défaut', 'pt': 'Predefinida',
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

# --- prepracovany onboarding (4 kroky s obrazom) ---
STRINGS.update({
    'ob.step1.kicker': {
        'sk': 'KROK 1 zo 4',
        'en': 'STEP 1 of 4',
        'ja': 'STEP 1 of 4',
        'zh': 'STEP 1 of 4',
        'ru': 'STEP 1 of 4',
        'es': 'STEP 1 of 4',
        'de': 'STEP 1 of 4',
        'fr': 'STEP 1 of 4',
        'pt': 'STEP 1 of 4',
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
    'ob.step1.body': {
        'sk': 'Pri clutchi telo stuhne skôr, než si to všimneš — zovretá čeľusť, zadržaný dych, kŕč v ruke. Zanshin netrénuje aim; trénuje odísť z hry pokojnejší, než si do nej vošiel.',
        'en': "In a clutch your body tightens before you notice — a clenched jaw, a held breath, a cramped hand. Zanshin doesn't train your aim; it trains you to leave the match calmer than you entered it.",
        'ja': "In a clutch your body tightens before you notice — a clenched jaw, a held breath, a cramped hand. Zanshin doesn't train your aim; it trains you to leave the match calmer than you entered it.",
        'zh': "In a clutch your body tightens before you notice — a clenched jaw, a held breath, a cramped hand. Zanshin doesn't train your aim; it trains you to leave the match calmer than you entered it.",
        'ru': "In a clutch your body tightens before you notice — a clenched jaw, a held breath, a cramped hand. Zanshin doesn't train your aim; it trains you to leave the match calmer than you entered it.",
        'es': "In a clutch your body tightens before you notice — a clenched jaw, a held breath, a cramped hand. Zanshin doesn't train your aim; it trains you to leave the match calmer than you entered it.",
        'de': "In a clutch your body tightens before you notice — a clenched jaw, a held breath, a cramped hand. Zanshin doesn't train your aim; it trains you to leave the match calmer than you entered it.",
        'fr': "In a clutch your body tightens before you notice — a clenched jaw, a held breath, a cramped hand. Zanshin doesn't train your aim; it trains you to leave the match calmer than you entered it.",
        'pt': "In a clutch your body tightens before you notice — a clenched jaw, a held breath, a cramped hand. Zanshin doesn't train your aim; it trains you to leave the match calmer than you entered it.",
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
        'sk': 'KROK 2 zo 4',
        'en': 'STEP 2 of 4',
        'ja': 'STEP 2 of 4',
        'zh': 'STEP 2 of 4',
        'ru': 'STEP 2 of 4',
        'es': 'STEP 2 of 4',
        'de': 'STEP 2 of 4',
        'fr': 'STEP 2 of 4',
        'pt': 'STEP 2 of 4',
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
        'sk': 'Bezpečné voči anti-cheatu — nič neinjektuje, nič nečíta z hry',
        'en': 'Anti-cheat safe — injects nothing, reads nothing from the game',
        'ja': 'Anti-cheat safe — injects nothing, reads nothing from the game',
        'zh': 'Anti-cheat safe — injects nothing, reads nothing from the game',
        'ru': 'Anti-cheat safe — injects nothing, reads nothing from the game',
        'es': 'Anti-cheat safe — injects nothing, reads nothing from the game',
        'de': 'Anti-cheat safe — injects nothing, reads nothing from the game',
        'fr': 'Anti-cheat safe — injects nothing, reads nothing from the game',
        'pt': 'Anti-cheat safe — injects nothing, reads nothing from the game',
    },
    'ob.step3.kicker': {
        'sk': 'KROK 3 zo 4 — nepovinné',
        'en': 'STEP 3 of 4 — optional',
        'ja': 'STEP 3 of 4 — optional',
        'zh': 'STEP 3 of 4 — optional',
        'ru': 'STEP 3 of 4 — optional',
        'es': 'STEP 3 of 4 — optional',
        'de': 'STEP 3 of 4 — optional',
        'fr': 'STEP 3 of 4 — optional',
        'pt': 'STEP 3 of 4 — optional',
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
        'sk': 'Kedy sa ozvať, rozhoduje tvoj tep — bez neho appka nemá z čoho poznať, že ti záťaž drží hore, a nepovie nič. Spárovať sa dá aj neskôr v Nastaveniach → Hodinky.',
        'en': 'Your heart rate decides when to speak — without it the app has no way to know your load is up, and says nothing. You can pair later in Settings → Watch.',
        'ja': 'いつ声をかけるかは心拍が決めます。心拍がなければ負荷が上がっていることを知る手段がなく、何も言いません。ペアリングは後から設定→時計でもできます。',
        'zh': '何时出声由你的心率决定——没有心率，应用无从得知你的负荷在升高，也就什么都不会说。之后可在设置→手表中配对。',
        'ru': 'Когда подать голос, решает твой пульс — без него приложение не может узнать, что нагрузка держится, и молчит. Связать часы можно позже: Настройки → Часы.',
        'es': 'Tu pulso decide cuándo hablar: sin él la app no tiene forma de saber que tu carga está alta y no dice nada. Puedes emparejar más tarde en Ajustes → Reloj.',
        'de': 'Dein Puls entscheidet, wann sie sich meldet — ohne ihn kann die App nicht wissen, dass deine Belastung oben bleibt, und sagt nichts. Koppeln geht später in Einstellungen → Uhr.',
        'fr': "C'est ton pouls qui décide quand parler — sans lui, l'app ne peut pas savoir que ta charge tient, et elle se tait. Tu peux appairer plus tard dans Réglages → Montre.",
        'pt': 'É o teu pulso que decide quando falar — sem ele o app não tem como saber que a tua carga está alta e não diz nada. Podes emparelhar depois em Definições → Relógio.',
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
        'sk': 'KROK 4 zo 4',
        'en': 'STEP 4 of 4',
        'ja': 'STEP 4 of 4',
        'zh': 'STEP 4 of 4',
        'ru': 'STEP 4 of 4',
        'es': 'STEP 4 of 4',
        'de': 'STEP 4 of 4',
        'fr': 'STEP 4 of 4',
        'pt': 'STEP 4 of 4',
    },
    'ob.step4.title': {
        'sk': 'Vyber vzhľad a vstúp',
        'en': 'Pick a look and step in',
        'ja': 'Pick a look and step in',
        'zh': 'Pick a look and step in',
        'ru': 'Pick a look and step in',
        'es': 'Pick a look and step in',
        'de': 'Pick a look and step in',
        'fr': 'Pick a look and step in',
        'pt': 'Pick a look and step in',
    },
    'ob.step4.body': {
        'sk': 'Farby sa dajú kedykoľvek zmeniť v Nastaveniach.',
        'en': 'You can change the colours any time in Settings.',
        'ja': 'You can change the colours any time in Settings.',
        'zh': 'You can change the colours any time in Settings.',
        'ru': 'You can change the colours any time in Settings.',
        'es': 'You can change the colours any time in Settings.',
        'de': 'You can change the colours any time in Settings.',
        'fr': 'You can change the colours any time in Settings.',
        'pt': 'You can change the colours any time in Settings.',
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
    'tour.triggers.body': {
        'sk': 'Tu si nastavíš, ČO appka povie — vetu, hlas a zvuk. KEDY sa ozve, rozhoduje tvoje telo: appka počká, kým ti záťaž chvíľu drží hore, a ozve sa v najbližšej prestávke. Ako často, si vyberáš hore. Prečo práve tieto štyri veci, si rozbalíš šípkou pri každej hláške.',
        'en': 'Here you set WHAT the app says — the line, the voice and the sound. WHEN it speaks is up to your body: it waits until your load holds up for a while, then speaks in the next break. How often is your choice at the top. Why these four things in particular, you can unfold with the arrow at each cue.',
        'ja': 'ここで決めるのはアプリが「何を」言うか — 文、声、音です。「いつ」話すかは体が決めます。負荷がしばらく続くのを待ち、次の小休止で声をかけます。頻度は上で選べます。 なぜこの4つなのかは、各セリフの矢印で開いて読めます。',
        'zh': '这里设置应用"说什么"——句子、语音和音效。"何时"出声由你的身体决定：等到负荷持续一段时间，再在下一个间隙出声。频率可在上方选择。 为什么偏偏是这四件事，可以点每条提示语旁的箭头展开。',
        'ru': 'Здесь ты задаёшь, ЧТО приложение скажет — фразу, голос и звук. КОГДА заговорит, решает тело: оно ждёт, пока нагрузка какое-то время держится, и говорит в ближайшей паузе. Как часто — выбираешь выше. Почему именно эти четыре вещи — раскроешь стрелкой у каждой реплики.',
        'es': 'Aquí eliges QUÉ dice la app: la frase, la voz y el sonido. CUÁNDO habla lo decide tu cuerpo: espera a que tu carga se mantenga un rato y habla en la siguiente pausa. Con qué frecuencia lo eliges arriba. Por qué justo estas cuatro cosas lo despliegas con la flecha de cada señal.',
        'de': 'Hier legst du fest, WAS die App sagt — Satz, Stimme und Ton. WANN sie spricht, entscheidet dein Körper: sie wartet, bis deine Belastung eine Weile oben bleibt, und meldet sich in der nächsten Pause. Wie oft, wählst du oben. Warum gerade diese vier Dinge, klappst du mit dem Pfeil bei jedem Hinweis auf.',
        'fr': "Ici tu choisis CE QUE l'app dit — la phrase, la voix et le son. QUAND elle parle, c'est ton corps qui décide : elle attend que ta charge tienne un moment, puis parle à la prochaine pause. À quelle fréquence, tu le choisis en haut. Pourquoi ces quatre choses-là, tu le déplies avec la flèche de chaque phrase.",
        'pt': 'Aqui defines O QUE o app diz — a frase, a voz e o som. QUANDO fala decide o teu corpo: espera que a carga se mantenha um pouco e fala na pausa seguinte. Com que frequência, escolhes em cima. Porquê estas quatro coisas, abres com a seta em cada fala.',
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
        'sk': 'Hlas aj zvukové efekty pripomienok. Dá sa vybrať hlas, hlasitosť aj vlastné nahrávky.',
        'en': 'The voice and sound effects for cues. You can pick the voice, volume, and even your own recordings.',
        'ja': 'The voice and sound effects for cues. You can pick the voice, volume, and even your own recordings.',
        'zh': 'The voice and sound effects for cues. You can pick the voice, volume, and even your own recordings.',
        'ru': 'The voice and sound effects for cues. You can pick the voice, volume, and even your own recordings.',
        'es': 'The voice and sound effects for cues. You can pick the voice, volume, and even your own recordings.',
        'de': 'The voice and sound effects for cues. You can pick the voice, volume, and even your own recordings.',
        'fr': 'The voice and sound effects for cues. You can pick the voice, volume, and even your own recordings.',
        'pt': 'The voice and sound effects for cues. You can pick the voice, volume, and even your own recordings.',
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
        'sk': 'Všetko, čo appka kreslí počas hrania — piktogramy, HUD tepu — a spárovanie hodiniek. Piktogramy si tu potiahneš tam, kam chceš.',
        'en': 'Everything the app draws while you play — icons, the heart-rate HUD — and watch pairing. You drag the icons wherever you want here.',
        'ja': 'Everything the app draws while you play — icons, the heart-rate HUD — and watch pairing. You drag the icons wherever you want here.',
        'zh': 'Everything the app draws while you play — icons, the heart-rate HUD — and watch pairing. You drag the icons wherever you want here.',
        'ru': 'Everything the app draws while you play — icons, the heart-rate HUD — and watch pairing. You drag the icons wherever you want here.',
        'es': 'Everything the app draws while you play — icons, the heart-rate HUD — and watch pairing. You drag the icons wherever you want here.',
        'de': 'Everything the app draws while you play — icons, the heart-rate HUD — and watch pairing. You drag the icons wherever you want here.',
        'fr': 'Everything the app draws while you play — icons, the heart-rate HUD — and watch pairing. You drag the icons wherever you want here.',
        'pt': 'Everything the app draws while you play — icons, the heart-rate HUD — and watch pairing. You drag the icons wherever you want here.',
    },
    'tour.guide.title': {
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
    'tour.guide.body': {
        'sk': 'Prečo to funguje — krátke vysvetlenie ku každej pripomienke a veda za tým.',
        'en': 'Why it works — a short explanation of each cue and the science behind it.',
        'ja': 'Why it works — a short explanation of each cue and the science behind it.',
        'zh': 'Why it works — a short explanation of each cue and the science behind it.',
        'ru': 'Why it works — a short explanation of each cue and the science behind it.',
        'es': 'Why it works — a short explanation of each cue and the science behind it.',
        'de': 'Why it works — a short explanation of each cue and the science behind it.',
        'fr': 'Why it works — a short explanation of each cue and the science behind it.',
        'pt': 'Why it works — a short explanation of each cue and the science behind it.',
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
    """sk + en rucne, ostatnych 7 jazykov zatial anglicky (na dopreklad -
    zoznam v preklad_TODO.csv). Rovnaka konvencia ako doteraz, len bez
    deviatich riadkov na kazdy kluc."""
    return {"sk": sk, "en": en, "ja": en, "zh": en, "ru": en, "es": en,
            "de": en, "fr": en, "pt": en}


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
        'Zatiaľ žiadna relácia. Zapni senzor tepu vo „V hre“, zahraj si aspoň minútu a po vypnutí sa relácia objaví tu.',
        'No sessions yet. Turn on the heart-rate sensor in “In game”, play for at least a minute, and the session shows up here once you stop.'),
    'history.insights_title': _sk_en('Čo si appka všimla', 'What the app noticed'),
    'history.insights_note': _sk_en(
        'Počíta sa na pozadí z celej histórie. Sú to postrehy a tipy, nie diagnózy.',
        'Computed in the background from your whole history. Observations and tips, not diagnoses.'),
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
    'history.col_triggers': _sk_en('Dýchanie', 'Breathing'),
    'history.col_peak': _sk_en('Špička záťaže', 'Peak load'),
    'history.col_hrr': _sk_en('HRR', 'HRR'),
    'history.col_hrpi': _sk_en('HRPI', 'HRPI'),
    'history.info_more': _sk_en('ⓘ čo to znamená', 'ⓘ what it means'),
    'history.info_less': _sk_en('ⓘ skryť', 'ⓘ hide'),
    'history.science_title': _sk_en('Prečo to funguje', 'Why it works'),
    'history.science_intro': _sk_en(
        'Zanshin nemeria tvoj tep pre zdravie — meria ho preto, aby vedel, kedy ti pomôcť sa upokojiť. Tu je veda, na ktorej to stojí:',
        'Zanshin does not measure your heart rate for health — it measures it to know when to help you calm down. Here is the science it stands on:'),
    'history.science_hrv_note': _sk_en(
        'Odkazy o HRV sú tu ako kontext o tepe a strese — appka HRV nemeria (potrebuje rozostupy medzi údermi, ktoré hodinky takto neposielajú).',
        'HRV links are here as context on heart rate and stress — the app does not measure HRV (it needs beat-to-beat intervals, which the watch does not send this way).'),

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
    'metric.breath.tag': _sk_en('dýchanie', 'breathing'),
    'metric.avg.tag': _sk_en('priemer', 'average'),
    'metric.max.tag': _sk_en('maximum', 'highest'),
    'metric.peak.tag': _sk_en('špička', 'peak load'),
    'metric.week.tag': _sk_en('týždeň', 'this week'),
    'metric.baseline.title': _sk_en('Pokojová základňa', 'Resting baseline'),
    'metric.baseline.short': _sk_en('Tvoj tep, keď ťa hra nikam netlačí.',
                                    'Your heart rate when the game is not pushing you.'),
    'metric.baseline.more': _sk_en(
        'Appka si ju počíta z tvojich najpokojnejších chvíľ. Keď stúpa deň za dňom, telo môže byť unavené alebo v strese — nie nutne z hrania (spánok, kofeín, choroba). Preto ju sledujeme v čase, nie jedno číslo.',
        'The app derives it from your calmest moments. When it climbs day after day, your body may be tired or stressed — not necessarily from gaming (sleep, caffeine, illness). That is why we track it over time, not as a single number.'),
    'metric.load.title': _sk_en('Záťaž', 'Load'),
    'metric.load.short': _sk_en('Ako veľmi ťa hra práve zaťažuje — z tvojho tepu, nie z HRV.',
                                'How hard the game is pushing you right now — from your heart rate, not HRV.'),
    'metric.load.more': _sk_en(
        'Skladá sa z troch vecí, ktoré sa z tepu naozaj dajú zistiť: o koľko si nad pokojom, ako rýchlo tep stúpa, a ako dlho ostáva hore. Nie je to HRV — to potrebuje rozostupy medzi údermi, ktoré hodinky takto neposielajú.',
        'It combines three things heart rate can actually tell: how far above resting you are, how fast it is climbing, and how long it stays up. It is not HRV — that needs beat-to-beat intervals, which the watch does not send this way.'),
    'metric.hrr.title': _sk_en('Zotavenie tepu (HRR)', 'Heart rate recovery (HRR)'),
    'metric.hrr.short': _sk_en('O koľko ti klesol tep za minútu po tom, čo vyskočil.',
                               'How much your heart rate dropped in the minute after it spiked.'),
    'metric.hrr.more': _sk_en(
        'Meria, ako rýchlo sa vieš upokojiť. Väčší pokles = rýchlejšie späť do pokoja. Bežne 12–23 úderov za minútu, trénovaní aj 29 a viac. Rýchlejšie zotavenie súvisí s lepšou kondíciou a zlepšuje sa tréningom.',
        'It measures how fast you can settle down. A bigger drop = back to calm sooner. Typically 12–23 beats per minute, trained people 29 and more. Faster recovery goes with better fitness and improves with training.'),
    'metric.zones.title': _sk_en('Čas nad hranicou / v pásmach', 'Time over limit / in zones'),
    'metric.zones.short': _sk_en('Koľko z relácie si strávil s vysokým tepom.',
                                 'How much of the session you spent with a high heart rate.'),
    'metric.zones.more': _sk_en(
        'Krátke špičky po headshote sú normálne. Dlhý čas nad hranicou znamená, že ťa hra drží v napätí — presne vtedy pomáha dýchanie, ktoré appka vie spustiť sama.',
        'Short spikes after a headshot are normal. A long time over the limit means the game keeps you tense — exactly when the breathing the app can trigger by itself helps.'),
    'metric.hrpi.title': _sk_en('HRPI', 'HRPI'),
    'metric.hrpi.short': _sk_en('Jedno číslo, ktoré spája, ako vysoko a ako dlho ti bil tep.',
                                'One number that ties together how high and how long your heart rate ran.'),
    'metric.hrpi.more': _sk_en(
        'Číslo k znamená, že tvoj tep bol aspoň k úderov za minútu po dobu aspoň k sekúnd. Spája výšku aj trvanie, takže dve relácie porovnáš jedným pohľadom.',
        'A value k means your heart rate was at least k beats per minute for at least k seconds. It joins height and duration, so you can compare two sessions at a glance.'),
    'metric.zones.calm': _sk_en('pokoj', 'calm'),
    'metric.zones.raised': _sk_en('zvýšená', 'raised'),
    'metric.zones.high': _sk_en('vysoká', 'high'),
    'metric.zones.critical': _sk_en('kritická', 'critical'),

    # --- vybratelne statistiky na Dnes (2x2 mriezka, "Sumi noc" redizajn) ---
    'dashboard.stats_title': _sk_en('Moje štatistiky', 'My stats'),
    'dashboard.edit_stats': _sk_en('✎ upraviť', '✎ edit'),
    'dashboard.picker_title': _sk_en('Čo chceš vidieť', 'What you want to see'),
    # kratky nazov pre kartu na Dnes (metric.zones.title je dlhsi, pre
    # rozbalitelnu vedu v Historii - obsah vysvetlenia (.short/.more) je
    # spolocny, len tento titulok je vlastny)
    'metric.over.more': {
        'sk': 'Koľko času tvoj tep strávil nad hranicou, ktorú si si nastavil („Tep, pri ktorom pomôcť"). Nie je to známka — krátke špičky patria k hre. Zaujímavé je to, keď číslo večer čo večer rastie pri rovnako dlhom hraní: vtedy telo z hry odchádza vo vyšších otáčkach, než do nej vošlo.',
        'en': 'How long your heart rate stayed above the limit you set ("Heart rate to help at"). It is not a grade — short spikes are part of playing. It matters when the number grows evening after evening at the same playtime: then your body leaves the game revved higher than it entered.',
        'ja': '設定したしきい値（「助けを出す心拍数」）を超えていた時間です。評価ではありません。短いスパイクはゲームの一部です。同じプレイ時間で夜ごとに増えていくときが問題で、体が入ったときより高い回転数で出ていることを意味します。',
        'zh': '你的心率高于你设定阈值（"在多少心率时帮忙"）的时长。这不是评分——短暂的峰值是游戏的一部分。值得注意的是：在同样的游戏时长下，这个数字一晚比一晚高，说明身体离开游戏时比进入时转速更高。',
        'ru': 'Сколько времени пульс держался выше заданного тобой порога («Пульс, при котором помочь»). Это не оценка — короткие всплески часть игры. Важно, когда число растёт вечер за вечером при той же длительности игры: тогда тело выходит из игры на более высоких оборотах, чем вошло.',
        'es': 'Cuánto tiempo estuvo tu pulso por encima del límite que fijaste ("Pulso al que ayudar"). No es una nota: los picos cortos son parte de jugar. Importa cuando el número crece noche tras noche con el mismo tiempo de juego: entonces el cuerpo sale del juego más revolucionado de lo que entró.',
        'de': 'Wie lange dein Puls über der von dir gesetzten Grenze lag („Puls, ab dem geholfen wird"). Das ist keine Note — kurze Spitzen gehören zum Spielen. Wichtig wird es, wenn die Zahl Abend für Abend bei gleicher Spieldauer steigt: dann verlässt der Körper das Spiel höher gedreht, als er hineinging.',
        'fr': "Combien de temps ton pouls est resté au-dessus du seuil que tu as fixé (« Pouls auquel aider »). Ce n'est pas une note : les pics courts font partie du jeu. Ce qui compte, c'est quand le nombre grimpe soir après soir à durée de jeu égale : le corps sort alors du jeu plus emballé qu'il n'y est entré.",
        'pt': 'Quanto tempo o teu pulso ficou acima do limite que definiste ("Pulso a partir do qual ajudar"). Não é uma nota — picos curtos fazem parte de jogar. Importa quando o número cresce noite após noite com o mesmo tempo de jogo: aí o corpo sai do jogo mais acelerado do que entrou.',
    },
    'metric.over.title': _sk_en('Čas nad hranicou', 'Time over the limit'),
    'metric.breath.title': _sk_en('Dýchanie spustené', 'Breathing triggered'),
    'metric.breath.short': _sk_en(
        'Koľkokrát appka sama spustila dychový kruh pri vysokom tepe.',
        'How many times the app started the breathing circle on its own at a high heart rate.'),
    'metric.breath.more': _sk_en(
        'Počíta sa sem len automatické spustenie (tep dlho nad hranicou) — nie chvíle, keď si dychový kruh spustil sám klávesom. Dĺžku nádychu a výdychu (v sekundách) si nastavíš v „Vizuály v hre“ pri slote Dych — kratší cyklus pomôže rýchlejšie sa upokojiť v strese, dlhší vedie k hlbšiemu dýchaniu.',
        'This counts only automatic triggers (heart rate held high for a while) — not times you started the breathing circle yourself with a key. You can set the length of the inhale and exhale (in seconds) in “Visuals in game” on the Breath slot — a shorter cycle helps you calm down faster under stress, a longer one leads to deeper breathing.'),
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
        'Záťaž skladá tri veci z tepu: o koľko si nad pokojom, ako rýchlo tep stúpa a ako dlho ostáva hore. Špička je najvyšší okamih tejto kombinácie.',
        'Load combines three things from your heart rate: how far above resting you are, how fast it is climbing, and how long it stays up. The peak is the single highest moment of that combination.'),
    'metric.week.title': _sk_en('Relácie tento týždeň', 'Sessions this week'),
    'metric.week.short': _sk_en(
        'Koľko relácií si tento týždeň odohral a koľko to bolo spolu času.',
        'How many sessions you have played this week and how much time that was in total.'),
    'metric.week.more': _sk_en(
        'Týždeň sa počíta od pondelka. Slúži len na prehľad, koľko toho appka tento týždeň zaznamenala.',
        'The week counts from Monday. It is just an overview of how much the app has logged this week.'),
    'dashboard.unit.baseline': _sk_en('BPM', 'BPM'),
    'dashboard.unit.hrr': _sk_en('BPM za minútu', 'BPM per minute'),
    'dashboard.unit.over': _sk_en('za dnešnú reláciu', "this session"),
    'dashboard.unit.breath': _sk_en('automaticky', 'automatic'),
    'dashboard.unit.avg': _sk_en('za reláciu', 'this session'),
    'dashboard.unit.max': _sk_en('špička dnes', "today's peak"),
    'dashboard.unit.peak': _sk_en('z 0–100', 'of 0-100'),

    # --- odporucania z analyzy na pozadi (postrehy, nie diagnozy) ---
    # Odporucania o TICHU. Jedine, ktore hracovi hovoria, co ma urobit -
    # preto stoja na cislach zo spustaca, nie na dojme z tepu.
    'insight.cue_dropouts': _sk_en('Tep za posledné večery {n}× vypadol a pri každom výpadku sa počítanie začína odznova — preto je hlášok málo. Maj hodinky pri telefóne (spájajú sa cez Bluetooth) a telefón blízko Wi‑Fi routra — keď sa vzdiaľuješ, vezmi telefón so sebou.',
                                    'Your pulse dropped out {n}× over the last evenings, and every dropout restarts the count — that is why there are few cues. Keep the watch near the phone (they pair over Bluetooth) and the phone on good Wi‑Fi — when you get up, take the phone with you.'),
    'insight.cue_never_above': _sk_en('Posledné {n} večery sa záťaž ani raz nedostala nad hranicu — takže sa appka nemala prečo ozvať. Ak ti to príde málo, skús znížiť hranicu tepu v nastaveniach hodiniek.',
                                       'Over the last {n} evenings your load never crossed the threshold, so the app had no reason to speak. If that feels like too little, try lowering the heart-rate ceiling in the watch settings.'),
    'insight.cue_almost': _sk_en('Záťaž hore bola, ale najdlhšie {sec} s v kuse — chýbalo do {need} s. Bolo to tesne: skús prepnúť „ako často sa ozvem“ o stupeň vyššie.',
                                  'Your load did rise, but the longest stretch was {sec} s — short of {need} s. It was close: try moving “how often I speak up” one step up.'),
    'insight.cue_far': _sk_en('Záťaž sa nad hranicu dostala, ale len na chvíľu — najdlhšie {sec} s z potrebných {need} s. Tvoje telo ide hore a dole rýchlejšie, než appka čaká. Stojí za to znížiť hranicu tepu, nie len skracovať čakanie.',
                               'Your load did cross the threshold, but only briefly — the longest stretch was {sec} s out of {need} s. Your body rises and falls faster than the app waits for. Worth lowering the heart-rate ceiling, not just shortening the wait.'),
    'insight.need_more': _sk_en(
        'Zatiaľ {n} z {need} relácií — po troch začne appka hľadať vzory naprieč nimi.',
        '{n} of {need} sessions so far — after three the app starts looking for patterns across them.'),
    'insight.resting_up': _sk_en(
        'Pokojový tep za posledný týždeň stúpol o {delta} BPM oproti predošlému — možno menej spánku, kofeín alebo nachladnutie? Nie je to nutne z hrania.',
        'Your resting heart rate rose by {delta} BPM this week versus the one before — maybe less sleep, caffeine or a cold? Not necessarily from gaming.'),
    'insight.resting_down': _sk_en(
        'Pokojový tep klesol o {delta} BPM oproti predošlému týždňu — telo vyzerá oddýchnutejšie.',
        'Your resting heart rate dropped by {delta} BPM versus the previous week — your body looks more rested.'),
    'insight.hrr_up': _sk_en(
        'Zotavenie tepu sa zlepšilo o {delta} BPM — upokojíš sa rýchlejšie než predtým.',
        'Heart rate recovery improved by {delta} BPM — you settle down faster than before.'),
    'insight.hrr_down': _sk_en(
        'Zotavenie tepu je o {delta} BPM pomalšie než predtým — po vypätí trvá dlhšie, kým klesne. Skús dýchanie hneď po vypätej situácii.',
        'Heart rate recovery is {delta} BPM slower than before — it takes longer to come down after a tense moment. Try breathing right after a clutch.'),
    'insight.triggers_early': _sk_en(
        '{share} % spustení dýchania prišlo v prvej hodine — začiatok relácie ťa rozbieha najviac; skús pokojnejší rozjazd alebo kratšie relácie.',
        '{share} % of breathing triggers came in the first hour — the start of a session winds you up the most; try a calmer warm-up or shorter sessions.'),
    'insight.triggers_late': _sk_en(
        '{share} % spustení dýchania prišlo až po dvoch hodinách — dlhé relácie ťa držia v napätí; skús kratšie relácie s prestávkou.',
        '{share} % of breathing triggers came after two hours — long sessions keep you tense; try shorter sessions with a break.'),
    'insight.over_up': _sk_en(
        'Čas nad hranicou v posledných reláciách vzrástol (priemer {minutes} min) — hra ťa drží v napätí dlhšie než predtým; presne vtedy pomáha dýchanie.',
        'Time over the limit has grown in recent sessions (average {minutes} min) — the game keeps you tense longer than before; that is exactly when breathing helps.'),
    'insight.steady': _sk_en(
        'Za posledných {n} relácií nič nevybočuje — tep, zotavenie aj čas nad hranicou sú stabilné.',
        'Nothing stands out across the last {n} sessions — heart rate, recovery and time over the limit are steady.'),

    # --- zdroje k tepu (spolocny zoznam so Sprievodcom, viz guide_content) ---
    'guide.philosophy.source6': {
        'sk': 'Cole et al. 1999, NEJM — zotavenie srdcovej frekvencie po záťaži',
        'en': 'Cole et al. 1999, NEJM - heart-rate recovery after exercise',
        'ja': 'Cole et al. 1999, NEJM - 運動後の心拍数回復',
        'zh': 'Cole et al. 1999, NEJM - 运动后心率恢复',
        'ru': 'Cole et al. 1999, NEJM - восстановление частоты сердечных сокращений после нагрузки',
        'es': 'Cole et al. 1999, NEJM - recuperación de la frecuencia cardíaca tras el ejercicio',
        'de': 'Cole et al. 1999, NEJM - Herzfrequenzerholung nach Belastung',
        'fr': "Cole et al. 1999, NEJM - récupération de la fréquence cardiaque après l'effort",
        'pt': 'Cole et al. 1999, NEJM - recuperação da frequência cardíaca após exercício',
    },
    'guide.philosophy.source7': _sk_en(
        'WHOOP — Heart Rate Recovery: prečo je rýchlejšie zotavenie znakom kondície',
        'WHOOP — Heart Rate Recovery: why faster recovery reflects fitness'),
    'guide.philosophy.source8': {
        'sk': 'Kim et al. 2018 — stres a variabilita srdcovej frekvencie (metaanalýza)',
        'en': 'Kim et al. 2018 - stress and heart-rate variability (meta-analysis)',
        'ja': 'Kim et al. 2018 - ストレスと心拍変動（メタ分析）',
        'zh': 'Kim et al. 2018 - 压力与心率变异性（荟萃分析）',
        'ru': 'Kim et al. 2018 - стресс и вариабельность сердечного ритма (метаанализ)',
        'es': 'Kim et al. 2018 - estrés y variabilidad de la frecuencia cardíaca (metaanálisis)',
        'de': 'Kim et al. 2018 - Stress und Herzfrequenzvariabilität (Metaanalyse)',
        'fr': 'Kim et al. 2018 - stress et variabilité de la fréquence cardiaque (méta-analyse)',
        'pt': 'Kim et al. 2018 - estresse e variabilidade da frequência cardíaca (metanálise)',
    },
    'guide.philosophy.source9': {
        'sk': 'Brosschot & Thayer 2006 — predĺžená stresová aktivácia a zdravie',
        'en': 'Brosschot & Thayer 2006 - prolonged stress activation and health',
        'ja': 'Brosschot & Thayer 2006 - 持続的なストレス活性化と健康',
        'zh': 'Brosschot & Thayer 2006 - 持续的应激激活与健康',
        'ru': 'Brosschot & Thayer 2006 - длительная стрессовая активация и здоровье',
        'es': 'Brosschot & Thayer 2006 - activación prolongada del estrés y salud',
        'de': 'Brosschot & Thayer 2006 - anhaltende Stressaktivierung und Gesundheit',
        'fr': 'Brosschot & Thayer 2006 - activation prolongée du stress et santé',
        'pt': 'Brosschot & Thayer 2006 - ativação prolongada do estresse e saúde',
    },
    'guide.philosophy.source10': _sk_en(
        'PubMed (2024) — „Heartbeats and high scores“: esport spúšťa stresovú odpoveď srdca a nervového systému',
        'PubMed (2024) — “Heartbeats and high scores”: esports triggers a cardiovascular and autonomic stress response'),
    'guide.philosophy.source11': {
        'sk': 'Zaccaro et al. 2018 — pomalé dýchanie a vagové upokojenie (systematický prehľad)',
        'en': 'Zaccaro et al. 2018 - slow breathing and vagal calm (systematic review)',
        'ja': 'Zaccaro et al. 2018 - ゆっくりした呼吸と迷走神経による鎮静（システマティックレビュー）',
        'zh': 'Zaccaro et al. 2018 - 缓慢呼吸与迷走神经镇静（系统综述）',
        'ru': 'Zaccaro et al. 2018 - медленное дыхание и вагусное успокоение (систематический обзор)',
        'es': 'Zaccaro et al. 2018 - respiración lenta y calma vagal (revisión sistemática)',
        'de': 'Zaccaro et al. 2018 - langsame Atmung und vagale Beruhigung (systematische Übersicht)',
        'fr': 'Zaccaro et al. 2018 - respiration lente et apaisement vagal (revue systématique)',
        'pt': 'Zaccaro et al. 2018 - respiração lenta e calma vagal (revisão sistemática)',
    },
    'guide.philosophy.source12': {
        'sk': 'Lehrer & Gevirtz 2014 — prečo pomalé dýchanie upokojuje (HRV biofeedback)',
        'en': 'Lehrer & Gevirtz 2014 - why slow breathing calms (HRV biofeedback)',
        'ja': 'Lehrer & Gevirtz 2014 - ゆっくりした呼吸が心を落ち着かせる理由（HRVバイオフィードバック）',
        'zh': 'Lehrer & Gevirtz 2014 - 缓慢呼吸为何令人平静（HRV生物反馈）',
        'ru': 'Lehrer & Gevirtz 2014 - почему медленное дыхание успокаивает (HRV-биообратная связь)',
        'es': 'Lehrer & Gevirtz 2014 - por qué la respiración lenta calma (biofeedback de HRV)',
        'de': 'Lehrer & Gevirtz 2014 - warum langsame Atmung beruhigt (HRV-Biofeedback)',
        'fr': 'Lehrer & Gevirtz 2014 - pourquoi la respiration lente apaise (biofeedback de HRV)',
        'pt': 'Lehrer & Gevirtz 2014 - por que a respiração lenta acalma (biofeedback de HRV)',
    },
    'guide.philosophy.source13': {
        'sk': 'Goessl et al. 2017 — HRV biofeedback znižuje stres (metaanalýza)',
        'en': 'Goessl et al. 2017 - HRV biofeedback lowers stress (meta-analysis)',
        'ja': 'Goessl et al. 2017 - HRVバイオフィードバックがストレスを軽減（メタ分析）',
        'zh': 'Goessl et al. 2017 - HRV生物反馈降低压力（荟萃分析）',
        'ru': 'Goessl et al. 2017 - HRV-биообратная связь снижает стресс (метаанализ)',
        'es': 'Goessl et al. 2017 - el biofeedback de HRV reduce el estrés (metaanálisis)',
        'de': 'Goessl et al. 2017 - HRV-Biofeedback senkt Stress (Metaanalyse)',
        'fr': 'Goessl et al. 2017 - le biofeedback de HRV réduit le stress (méta-analyse)',
        'pt': 'Goessl et al. 2017 - o biofeedback de HRV reduz o estresse (metanálise)',
    },
    'guide.philosophy.source14': {
        'sk': 'Goyal et al. 2014, JAMA — mindfulness pri úzkosti (metaanalýza)',
        'en': 'Goyal et al. 2014, JAMA - mindfulness for anxiety (meta-analysis)',
        'ja': 'Goyal et al. 2014, JAMA - 不安に対するマインドフルネス（メタ分析）',
        'zh': 'Goyal et al. 2014, JAMA - 针对焦虑的正念（荟萃分析）',
        'ru': 'Goyal et al. 2014, JAMA - осознанность при тревоге (метаанализ)',
        'es': 'Goyal et al. 2014, JAMA - mindfulness para la ansiedad (metaanálisis)',
        'de': 'Goyal et al. 2014, JAMA - Achtsamkeit bei Angst (Metaanalyse)',
        'fr': "Goyal et al. 2014, JAMA - pleine conscience pour l'anxiété (méta-analyse)",
        'pt': 'Goyal et al. 2014, JAMA - mindfulness para ansiedade (metanálise)',
    },
    'guide.philosophy.source15': {
        'sk': 'van der Zwan et al. 2015 — dýchanie/mindfulness vs cvičenie (RCT)',
        'en': 'van der Zwan et al. 2015 - breathing/mindfulness vs exercise (RCT)',
        'ja': 'van der Zwan et al. 2015 - 呼吸法/マインドフルネス vs 運動（RCT）',
        'zh': 'van der Zwan et al. 2015 - 呼吸/正念 vs 运动（RCT）',
        'ru': 'van der Zwan et al. 2015 - дыхание/осознанность vs физические упражнения (RCT)',
        'es': 'van der Zwan et al. 2015 - respiración/mindfulness vs ejercicio (RCT)',
        'de': 'van der Zwan et al. 2015 - Atmung/Achtsamkeit vs Bewegung (RCT)',
        'fr': 'van der Zwan et al. 2015 - respiration/pleine conscience vs exercice (RCT)',
        'pt': 'van der Zwan et al. 2015 - respiração/mindfulness vs exercício (RCT)',
    },
    'guide.philosophy.source16': {
        'sk': 'MacLean et al. 2010 — meditácia zostruje trvalú pozornosť',
        'en': 'MacLean et al. 2010 - meditation sharpens sustained attention',
        'ja': 'MacLean et al. 2010 - 瞑想が持続的注意を高める',
        'zh': 'MacLean et al. 2010 - 冥想增强持续性注意',
        'ru': 'MacLean et al. 2010 - медитация улучшает устойчивое внимание',
        'es': 'MacLean et al. 2010 - la meditación agudiza la atención sostenida',
        'de': 'MacLean et al. 2010 - Meditation schärft die Daueraufmerksamkeit',
        'fr': "MacLean et al. 2010 - la méditation aiguise l'attention soutenue",
        'pt': 'MacLean et al. 2010 - a meditação aguça a atenção sustentada',
    },
    'guide.philosophy.source17': {
        'sk': 'Lutz et al. 2008 — regulácia pozornosti pri meditácii (prehľad)',
        'en': 'Lutz et al. 2008 - attention regulation in meditation (review)',
        'ja': 'Lutz et al. 2008 - 瞑想における注意の調整（レビュー）',
        'zh': 'Lutz et al. 2008 - 冥想中的注意调节（综述）',
        'ru': 'Lutz et al. 2008 - регуляция внимания при медитации (обзор)',
        'es': 'Lutz et al. 2008 - regulación de la atención en la meditación (revisión)',
        'de': 'Lutz et al. 2008 - Aufmerksamkeitsregulation bei Meditation (Übersicht)',
        'fr': "Lutz et al. 2008 - régulation de l'attention dans la méditation (revue)",
        'pt': 'Lutz et al. 2008 - regulação da atenção na meditação (revisão)',
    },

    # --- onboarding krok 3: druhy dovod pre hodinky (historia) ---
    'ob.step3.body2': _sk_en(
        'A ešte: appka si pamätá každú reláciu. Po pár dňoch ti ukáže, či sa upokojuješ rýchlejšie a či ťa hra zaťažuje menej — čierne na bielom, nie pocitovo.',
        "And one more thing: the app remembers every session. After a few days it shows whether you're calming down faster and whether the game strains you less — in plain numbers, not by feel."),

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
    'dock.snooze_active_tip': _sk_en('Stíšené — zostáva {minutes} min',
                                     'Snoozed — {minutes} min left'),
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
        'Keď spáruješ hodinky, appka ti sem kreslí tep, záťaž a sama spustí dýchanie, keď to bude treba.',
        'Once you pair your watch, the app draws your heart rate and load here and triggers breathing by itself when needed.'),
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
    'slots.hint': _sk_en(
        'Kedy sa ozve, rozhoduje tvoje telo — appka čaká, kým ti záťaž chvíľu drží hore, a ozve sa v najbližšej prestávke. Tu si nastavíš, čo presne povie. „Hlas + zvuk“ prehrá oboje.',
        'When it speaks is decided by your body — the app waits until your load stays up for a while, then speaks in the next pause. Here you set what it actually says. “Voice + sound” plays both.'),
    'settings.auto_profile': _sk_en('Prepínaj profil sám podľa hry, ktorá práve beží',
                                    'Switch the profile by itself based on the running game'),
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
    'guide.block.science': _sk_en('Čo na to veda', 'What science says'),
    'guide.block.instruction': _sk_en('Čo spraviť ty', 'What you do'),
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
                            'Once connected, pick the scene “Zanshin” and the source “Heart rate”. If you can also send steps and speed, the sources “Kroky” and “Rychlost” are there too.'),
    'hr.step5_body': _sk_en('Vráť sa sem a zapni „Počúvať tep z hodiniek“. Tep uvidíš do pár sekúnd.',
                            'Come back here and turn on “Listen for heart rate from the watch”. You will see it within seconds.'),
    'hr.trouble_body': _sk_en(
        'Skontroluj scénu „Zanshin“ a zdroj „Tep“ v telefóne a či hodinky naozaj merajú. Pri prvom spustení Windows spýta, či appku pustiť do siete — ak si to odmietol, hodinky sa nepripoja (povoľ ju vo firewalle). Ak port obsadil iný program, zmeň ho tu aj v telefóne.',
        'Check the “Zanshin” scene and “Heart rate” source on the phone, and that the watch is actually measuring. On first run Windows asks whether to allow the app on the network — if you declined, the watch cannot connect (allow it in the firewall). If another program took the port, change it here and on the phone.'),
    'hr.pair_other_ips': _sk_en('Ďalšie adresy tohto PC (ak prvá nejde): {ips}',
                                'Other addresses of this PC (if the first does not work): {ips}'),
    'hr.pair_ip_note': _sk_en('V nastaveniach nechaj 0.0.0.0 — toto číslo ide len do telefónu.',
                              'Keep 0.0.0.0 in settings — this number only goes into the phone.'),

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
        'Malý panel s tepom a 4 základnými funkciami priamo v hre — pre toho, kto nechce plné vizuály na obrazovke.',
        'A small panel with heart rate and the 4 basic functions right in-game — for anyone who wants fewer visuals on screen.'),
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
    'log.hotkey_failed': _sk_en('Skratku {combo} drží iná aplikácia — stíšiť sa dá aj spínačom v páse hore alebo cez ikonu v lište', 'Another app holds {combo} — you can still silence it with the switch in the top bar or the tray icon'),
    'log.snooze_started': _sk_en('Appka stíšená na {minutes} minút', 'App snoozed for {minutes} minutes'),
    'log.snooze_ended': _sk_en('Stíšenie skončilo', 'Snooze ended'),
    'log.snooze_cancelled': _sk_en('Stíšenie zrušené', 'Snooze cancelled'),
})


# --- Grafy na stránkach Dnes a História -----------------------------------
# Stopa relácie, rozdelenie času v pásmach, odchýlka na kartách, osi a
# mriežka dní. Ton je rovnaký ako inde: čo vidíme, nie čo to o tebe hovorí.
STRINGS.update({
    'dnes.trace_title': _sk_en('Stopa relácie', 'Session trace'),
    'dnes.trace_meta': _sk_en('{time} · dýchanie {n}×', '{time} · breathing {n}x'),
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
        'Hlasitosť, pomer, rýchlosť reči, pauza aj prekrývanie sa vrátia na '
        'hodnoty, s ktorými appka prišla. Vybraný hlas ostane.',
        'Volume, mix, speech speed, pause and overlap go back to the values the '
        'app shipped with. Your chosen voice stays.'),
    'settings.audio_reset_btn': _sk_en('Vrátiť', 'Restore'),
    # --- export relacii do tabulky ----------------------------------------
    'history.export_btn': _sk_en('Exportovať do tabuľky', 'Export to a spreadsheet'),
    'history.export_filetype': _sk_en('Tabuľka pre Excel (CSV)', 'Excel spreadsheet (CSV)'),
    'history.export_local': _sk_en(
        'Tep, relácie ani nastavenia appka nikam neposiela — sú v tvojom '
        'počítači a súbor si uložíš, kam chceš.',
        'Your heart rate, sessions and settings never leave this computer — '
        'the app sends them nowhere, and you choose where the file goes.'),
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
    'history.export_col.breathing': _sk_en('Dýchanie spustené', 'Breathing triggered'),
    'history.export_col.peak_stress': _sk_en('Špička záťaže', 'Peak load'),
    'history.export_col.hrr_bpm': _sk_en('Zotavenie (HRR)', 'Recovery (HRR)'),
    'history.export_col.hrpi': _sk_en('HRPI', 'HRPI'),
    'history.export_col.calm_min': _sk_en('Pokoj (min)', 'Calm (min)'),
    'history.export_col.raised_min': _sk_en('Zvýšená (min)', 'Raised (min)'),
    'history.export_col.high_min': _sk_en('Vysoká (min)', 'High (min)'),
    'history.export_col.critical_min': _sk_en('Kritická (min)', 'Critical (min)'),

    # uistenie o lokalnych datach - aj v onboardingu, hned pri anti-cheate
    'ob.step2.tag_local': _sk_en(
        'Tep aj relácie zostávajú v tvojom počítači — a kedykoľvek si ich '
        'vyexportuješ do tabuľky',
        'Heart rate and sessions stay on your computer — and you can export '
        'them to a spreadsheet any time'),

    # --- prehliadka: tepova polovica appky + pokracovanie -----------------
    'tour.sensor.title': _sk_en('Hodinky a tep', 'Watch and heart rate'),
    'tour.sensor.body': _sk_en(
        'Tu appke povieš, kde ťa má počúvať. Keď jej dáš svoj tep, spustí '
        'dýchací kruh sama — presne vtedy, keď si na to v zápale hry '
        'nespomenieš. Bez hodiniek funguje všetko ostatné rovnako.',
        'This is where you tell the app where to listen. Give it your heart '
        'rate and it starts the breathing circle on its own — exactly when you '
        'would not think of it. Everything else works the same without a watch.'),
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
    'hr.qr_ios': _sk_en(
        'iPhone / Apple Watch\n„PulseOSC“ (platená).\nPosiela OSC — nastav '
        'v nej IP a port tohto PC.',
        'iPhone / Apple Watch\n"PulseOSC" (paid).\nSends OSC — set this PC\'s '
        'IP and port inside it.'),
    'hr.qr_note': _sk_en(
        'Obe appky sú cudzie, nie naše — my ich len vieme počúvať.',
        'Both apps belong to someone else, not us — we just listen to them.'),
    # Povodny text sluboval "HeartRateOnStream (Google Play / App Store)" -
    # lenze tá appka na App Store nie je a na iPhone ziadna appka
    # protokolom obs-websocket nehovori. Na iOS treba OSC (PulseOSC).
    'hr.step2_body': _sk_en(
        'Android / Wear OS: „HeartRateOnStream for OBS“ z Google Play. '
        'iPhone / Apple Watch: „PulseOSC“ z App Store — posiela OSC, ktoré '
        'appka tiež rozumie. Naskenuj kód nižšie a prepoj ju s hodinkami.',
        'Android / Wear OS: "HeartRateOnStream for OBS" from Google Play. '
        'iPhone / Apple Watch: "PulseOSC" from the App Store — it sends OSC, '
        'which this app also understands. Scan a code below and connect it '
        'to your watch.'),

    # --- onboarding: opravy prvych styroch krokov -------------------------
    # Stvrty piktogram (appka instaluje STYRI spustace, krok ukazoval tri),
    # veta o mechanizme (nikde v uvode nebolo, ze to visi na klavesoch, ktore
    # hrac aj tak tlaci) a CTA, ktore nesluboval vstup do hry.
    'ob.step1.cap_release': _sk_en('Uvoľni ruku', 'Loosen grip'),
    'ob.step1.how': {
        'sk': 'Nemusíš nič stláčať ani si nič pamätať — appka sleduje tvoje zaťaženie a ozve sa sama v najbližšej prestávke.',
        'en': 'You do not have to press or remember anything — the app watches your load and speaks up by itself in the next break.',
        'ja': '何かを押したり覚えたりする必要はありません。アプリが負荷を見て、次の小休止で自分から声をかけます。',
        'zh': '你不用按任何键，也不用记住什么——应用会观察你的负荷，在下一个间隙自己出声。',
        'ru': 'Тебе не нужно ничего нажимать и ничего запоминать — приложение следит за нагрузкой и само подаёт голос в ближайшей паузе.',
        'es': 'No tienes que pulsar ni recordar nada: la app observa tu carga y habla sola en la siguiente pausa.',
        'de': 'Du musst nichts drücken und dir nichts merken — die App beobachtet deine Belastung und meldet sich von selbst in der nächsten Pause.',
        'fr': "Tu n'as rien à presser ni à retenir — l'app surveille ta charge et parle d'elle-même à la prochaine pause.",
        'pt': 'Não tens de carregar em nada nem lembrar-te de nada — o app observa a tua carga e fala sozinho na pausa seguinte.',
    },
    'onboarding.confirm': _sk_en('Hotovo — spustiť', 'Done — start'),
    'ob.step3.later_note': _sk_en(
        'Nechceš teraz? Pokračuj tlačidlom Ďalej — spárovať sa dá kedykoľvek '
        'vo „V hre → Ako spárovať hodinky“.',
        'Not now? Just hit Next — you can pair any time under "In game → How to '
        'pair a watch".'),

    'settings.theme_sub': _sk_en(
        'Aizome je indigová, Sumi atramentová so zlatom. Prepína sa okamžite, '
        'skús obe.',
        'Aizome is indigo, Sumi is ink with gold. It switches instantly — try both.'),
    'log.audio_reset': _sk_en('Zvuk vrátený na odporúčané hodnoty',
                              'Sound restored to recommended values'),

    'history.pick_metric': _sk_en('Metrika', 'Metric'),
    'history.pick_period': _sk_en('Obdobie', 'Period'),
    'history.band_label': _sk_en('tvoje bežné rozpätie', 'your usual range'),
    'history.unit.baseline': _sk_en('BPM', 'BPM'),
    'history.unit.hrr': _sk_en('BPM za minútu', 'BPM per minute'),
    'history.unit.over': _sk_en('minúty', 'minutes'),
    'history.unit.peak': _sk_en('z 0–100', 'of 0-100'),

    'history.effect_title': _sk_en('Ktorá hláška zaberá',
                                   'Which cue works'),
    'history.effect_hint': _sk_en(
        'Posun tepu po hláške. Vľavo od stredu znamená, že tep klesol. Tenká čiarka je rozsah, v ktorom sa skutočná hodnota pravdepodobne nachádza — kým presahuje stred, rozdiel môže byť aj opačný.',
        'How your pulse moved after a cue. Left of centre means it dropped. The thin line is the range the true value likely sits in — while it crosses the centre, the difference could go either way.'),
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
    'history.detail_breath': _sk_en('Dýchanie', 'Breathing'),
    'history.detail_hrpi': _sk_en('HRPI', 'HRPI'),
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
_tr7('app.version_short', 'alpha 0.1', 'alpha 0.1', 'alpha 0.1', 'alpha 0.1', 'Alpha 0.1', 'alpha 0.1', 'alpha 0.1')
_tr7('common.open', '開く', '打开', 'Открыть', 'Abrir', 'Öffnen', 'Ouvrir', 'Abrir')
_tr7('dialog.timing_title', 'タイミング', '时机', 'Тайминг', 'Tiempos', 'Timing', 'Rythme', 'Tempo')
_tr7('dock.pulse_live_tip', '心拍を受信中', '正在接收心率', 'Пульс поступает', 'Pulso en directo', 'Puls kommt an', 'Le pouls arrive', 'Pulso ao vivo')
_tr7('dock.snooze_active_tip', 'スヌーズ中 — 残り {minutes} 分', '已暂停 — 还剩 {minutes} 分钟', 'Пауза — осталось {minutes} мин', 'En pausa — quedan {minutes} min', 'Pausiert — noch {minutes} Min', 'En pause — {minutes} min restantes', 'Em pausa — faltam {minutes} min')
_tr7('dock.start', '▶  開始', '▶  开始', '▶  Запустить', '▶  Iniciar', '▶  Starten', '▶  Démarrer', '▶  Iniciar')
_tr7('dock.stop', '■  停止', '■  停止', '■  Остановить', '■  Detener', '■  Stoppen', '■  Arrêter', '■  Parar')
_tr7('dock.stop_tip', '監視を停止 — 再開するまで何も鳴らない', '停止监听 — 重新开始前不会触发任何内容', 'Перестать слушать — пока не запустишь снова, ничего не сработает', 'Deja de escuchar: no se dispara nada hasta que vuelvas a empezar', 'Nicht mehr zuhören — bis zum Neustart passiert nichts', "Arrêter d'écouter — plus rien ne se déclenche jusqu'au redémarrage", 'Para de ouvir — nada dispara até você recomeçar')
_tr7('engine.edge', '自然な音声（Edge、準備にネット接続が必要）', '自然语音（Edge，准备时需要联网）', 'Естественный голос (Edge, для подготовки нужен интернет)', 'Voz natural (Edge, necesita internet para prepararse)', 'Natürliche Stimme (Edge, braucht Internet zur Vorbereitung)', 'Voix naturelle (Edge, nécessite internet pour la préparation)', 'Voz natural (Edge, precisa de internet para preparar)')
_tr7('engine.sapi', 'Windows の音声（オフラインでも動く）', 'Windows 语音（离线也能用）', 'Голос Windows (работает без интернета)', 'Voz de Windows (funciona sin conexión)', 'Windows-Stimme (funktioniert offline)', 'Voix Windows (fonctionne hors ligne)', 'Voz do Windows (funciona offline)')
_tr7('kamae.running','監視中', '监听中', 'Слушаю', 'Escuchando', 'Hört zu', 'À l’écoute', 'Ouvindo')
_tr7('kamae.running_sub', '心拍を見ながら、いい頃合いを待っています。', '正在关注心率，等待合适的时机。', 'Слежу за пульсом и жду подходящий момент.', 'Vigilo tu pulso y espero el momento adecuado.', 'Ich beobachte deinen Puls und warte auf den richtigen Moment.', 'Je surveille ton pouls et j’attends le bon moment.', 'Acompanho o teu ritmo cardíaco e espero o momento certo.')
_tr7('sidebar.state_tip', '緑 — 監視中。赤 — 停止中。「今日」ページのバーで開始できます。', '绿色 — 正在监听。红色 — 未监听。可在「今天」页面的横条开始。', 'Зелёный — приложение слушает. Красный — нет. Запуск в полосе на странице «Сегодня».', 'Verde: la app escucha. Rojo: no. Se inicia en la barra de la página Hoy.', 'Grün — die App hört zu. Rot — nicht. Starten kannst du sie in der Leiste auf der Seite Heute.', 'Vert — l’app écoute. Rouge — non. Tu la démarres dans la barre de la page Aujourd’hui.', 'Verde — a app está a ouvir. Vermelho — não. Inicia-a na barra da página Hoje.')
_tr7('kamae.armed', '構えました', '已蓄势', 'Наготове', 'Preparada', 'Bereit', 'Prête', 'Pronta')
_tr7('kamae.armed_sub', '体がしばらく上がっています。いい頃合いを待ちます。', '你的身体已经紧绷了一阵子。我会等一个合适的时机。', 'Тело уже какое-то время на взводе. Подожду подходящий момент.', 'Llevas un rato con el cuerpo tenso. Esperaré un buen momento.', 'Dein Körper ist schon eine Weile oben. Ich warte auf einen guten Moment.', 'Ton corps est tendu depuis un moment. J’attendrai le bon moment.', 'O teu corpo está em tensão há algum tempo. Vou esperar um bom momento.')
_tr7('dnes.lastcue', '最後に話したのは {min} 分前 · {label}', '上次开口是 {min} 分钟前 · {label}', 'В последний раз — {min} мин назад · {label}', 'Habló por última vez hace {min} min · {label}', 'Zuletzt vor {min} Min · {label}', 'Dernière fois il y a {min} min · {label}', 'Falou pela última vez há {min} min · {label}')
_tr7('dnes.lastcue_now', 'たった今話しました · {label}', '刚刚开口 · {label}', 'Только что · {label}', 'Acaba de hablar · {label}', 'Gerade eben · {label}', 'À l’instant · {label}', 'Acabou de falar · {label}')
_tr7('kamae.stopped', '停止中', '已停止', 'Остановлено', 'Detenido', 'Gestoppt', 'Arrêté', 'Parado')
_tr7('kamae.stopped_sub', '何も見ていません。左のボタンで開始できます。', '什么都没在看。用左边的按钮开始。', 'Ничего не отслеживаю. Запусти кнопкой слева.', 'No vigilo nada. Iníciame con el botón de la izquierda.', 'Ich beobachte nichts. Starte mich mit dem Knopf links.', 'Je ne surveille rien. Démarre-moi avec le bouton à gauche.', 'Não acompanho nada. Inicia-me com o botão à esquerda.')
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
_tr7('ob.next', '次へ', '下一步', 'Далее', 'Siguiente', 'Weiter', 'Suivant', 'Seguinte')
_tr7('ob.skip', 'イントロをスキップ', '跳过介绍', 'Пропустить вступление', 'Saltar la introducción', 'Intro überspringen', "Passer l'intro", 'Saltar a introdução')
_tr7('ob.step1.kicker', 'ステップ 1 / 4', '第 1 步，共 4 步', 'ШАГ 1 из 4', 'PASO 1 de 4', 'SCHRITT 1 von 4', 'ÉTAPE 1 sur 4', 'PASSO 1 de 4')
_tr7('ob.step2.kicker', 'ステップ 2 / 4', '第 2 步，共 4 步', 'ШАГ 2 из 4', 'PASO 2 de 4', 'SCHRITT 2 von 4', 'ÉTAPE 2 sur 4', 'PASSO 2 de 4')
_tr7('ob.step3.kicker', 'ステップ 3 / 4 — 任意', '第 3 步，共 4 步 — 可选', 'ШАГ 3 из 4 — необязательно', 'PASO 3 de 4 — opcional', 'SCHRITT 3 von 4 — optional', 'ÉTAPE 3 sur 4 — facultatif', 'PASSO 3 de 4 — opcional')
_tr7('ob.step4.kicker', 'ステップ 4 / 4', '第 4 步，共 4 步', 'ШАГ 4 из 4', 'PASO 4 de 4', 'SCHRITT 4 von 4', 'ÉTAPE 4 sur 4', 'PASSO 4 de 4')
_tr7('ob.step1.title', 'ゲーム中にアプリが思い出させてくれること', '游戏中，应用会提醒你这些', 'Вот о чём приложение напомнит тебе в игре', 'Esto es lo que la app te recuerda en plena partida', 'Daran erinnert dich die App mitten im Spiel', 'Voici ce que l’app te rappelle en pleine partie', 'É disto que o app te lembra no meio do jogo')
_tr7('ob.step1.body', 'クラッチの場面では、気づく前に体がこわばる — 食いしばった顎、止まった呼吸、こわばった手。Zanshin はエイムを鍛えるのではなく、入ったときより静かに試合を出る力を鍛える。', '关键时刻，身体在你察觉之前就绷紧了 — 咬紧的下巴、憋住的呼吸、僵硬的手。Zanshin 练的不是准星，而是让你比进场时更平静地离场。', 'В решающий момент тело напрягается раньше, чем ты это замечаешь: сжатая челюсть, задержанное дыхание, судорога в руке. Zanshin тренирует не прицел, а умение выйти из матча спокойнее, чем ты в него вошёл.', 'En un clutch el cuerpo se tensa antes de que lo notes: mandíbula apretada, respiración contenida, mano agarrotada. Zanshin no entrena tu puntería; entrena salir de la partida más tranquilo de lo que entraste.', 'In einer Clutch verspannt sich der Körper, bevor du es merkst — zusammengebissener Kiefer, angehaltener Atem, verkrampfte Hand. Zanshin trainiert nicht dein Zielen, sondern dass du ruhiger aus dem Match gehst, als du hineingegangen bist.', 'Dans un clutch, le corps se crispe avant que tu le remarques : mâchoire serrée, souffle bloqué, main crispée. Zanshin n’entraîne pas la visée ; il entraîne à sortir du match plus calme qu’en y entrant.', 'Num clutch o corpo tensiona antes de repares — maxilar cerrado, respiração presa, mão travada. O Zanshin não treina a tua mira; treina sair da partida mais calmo do que entraste.')
_tr7('ob.step1.cap_grounding', '重心', '重心', 'Центр тяжести', 'Centro', 'Schwerpunkt', 'Ancrage', 'Centro')
_tr7('ob.step1.cap_jaw', '顎をゆるめる', '松开下巴', 'Расслабь челюсть', 'Afloja la mandíbula', 'Kiefer lockern', 'Relâche la mâchoire', 'Solta o maxilar')
_tr7('ob.step1.cap_release', '手をゆるめる', '松开握力', 'Расслабь руку', 'Afloja la mano', 'Griff lockern', 'Relâche la main', 'Solta a mão')
_tr7('ob.step1.cap_breath', '呼吸', '呼吸', 'Дыхание', 'Respiración', 'Atem', 'Souffle', 'Respiração')
_tr7('ob.step2.title', '控えめに。邪魔にならない隅に。', '低调。在角落，不挡路。', 'Незаметно. В углу, не мешая.', 'Discreto. En una esquina, sin estorbar.', 'Unaufdringlich. In der Ecke, nicht im Weg.', 'Discret. Dans un coin, hors du passage.', 'Discreto. Num canto, fora do caminho.')
_tr7('ob.step2.body', '合図は画面の端に出て、すぐ消える — クロスヘアやキルフィードを隠すことはない。位置は好きなところへドラッグでき、ゲーム中のクリックはそのままゲームに通る。', '提示出现在屏幕边缘随后淡出 — 绝不遮挡准星或击杀信息。位置可以随意拖动，游戏中的点击会直接穿透到游戏里。', 'Подсказки появляются у края экрана и гаснут — они никогда не закрывают прицел или киллфид. Всё можно перетащить куда хочешь, а клики в игре проходят прямо в игру.', 'Los avisos aparecen en el borde de la pantalla y se desvanecen: nunca tapan la mira ni el killfeed. Todo se puede arrastrar donde quieras y, en el juego, tus clics pasan directos al juego.', 'Die Hinweise erscheinen am Bildschirmrand und verschwinden wieder — sie verdecken nie Fadenkreuz oder Killfeed. Alles lässt sich hinziehen, wohin du willst, und im Spiel gehen deine Klicks direkt durch.', 'Les repères apparaissent au bord de l’écran puis s’effacent — ils ne couvrent jamais le viseur ni le killfeed. Tout se déplace où tu veux, et en jeu tes clics passent directement au jeu.', 'Os avisos aparecem na margem do ecrã e desvanecem — nunca tapam a mira nem o killfeed. Podes arrastar tudo para onde quiseres e, no jogo, os cliques passam direto para o jogo.')
_tr7('ob.step2.tag_safe', 'アンチチート的に安全 — 何も注入せず、ゲームからは何も読まない', '对反作弊安全 — 不注入任何东西，也不读取游戏', 'Безопасно для анти-чита — ничего не внедряет и ничего не читает из игры', 'Seguro frente al anti-cheat: no inyecta nada ni lee nada del juego', 'Anti-Cheat-sicher — injiziert nichts, liest nichts aus dem Spiel', 'Sans risque pour l’anti-triche — n’injecte rien, ne lit rien du jeu', 'Seguro para o anti-cheat — não injeta nada nem lê nada do jogo')
_tr7('ob.step2.tag_local', '心拍もセッションもこのPCに残る — いつでも表に書き出せる', '心率和记录都留在你的电脑里 — 随时可以导出成表格', 'Пульс и сессии остаются на твоём компьютере — и в любой момент их можно выгрузить в таблицу', 'El pulso y las sesiones se quedan en tu ordenador, y puedes exportarlos a una hoja de cálculo cuando quieras', 'Puls und Sitzungen bleiben auf deinem Rechner — und du kannst sie jederzeit als Tabelle exportieren', 'Le pouls et les séances restent sur ton ordinateur — et tu peux les exporter en tableur quand tu veux', 'O pulso e as sessões ficam no teu computador — e podes exportá-los para uma folha de cálculo quando quiseres')
_tr7('ob.step3.body2', 'もう一つ：アプリはすべてのセッションを覚えている。数日たてば、落ち着くのが速くなったか、ゲームの負荷が減ったかが見える — 感覚ではなく、はっきりした数字で。', '还有一点：应用会记住每一次记录。几天之后就能看出你是否更快平静下来、游戏是否没那么让你紧绷 — 用实打实的数字，而不是感觉。', 'И ещё: приложение помнит каждую сессию. Через несколько дней оно покажет, быстрее ли ты успокаиваешься и меньше ли тебя нагружает игра — числами, а не на ощущение.', 'Y una cosa más: la app recuerda cada sesión. A los pocos días te enseña si te calmas más rápido y si el juego te exige menos, en números claros y no por sensación.', 'Und noch etwas: Die App merkt sich jede Sitzung. Nach ein paar Tagen zeigt sie, ob du schneller runterkommst und ob dich das Spiel weniger belastet — in klaren Zahlen, nicht nach Gefühl.', 'Et encore une chose : l’app se souvient de chaque séance. Au bout de quelques jours, elle montre si tu te calmes plus vite et si le jeu te pèse moins — en chiffres, pas au feeling.', 'E mais uma coisa: o app lembra-se de cada sessão. Ao fim de uns dias mostra se te acalmas mais depressa e se o jogo te exige menos — em números, não por sensação.')
_tr7('ob.step3.pair_now', '今すぐ時計をつなぐ', '现在连接手表', 'Подключить часы сейчас', 'Vincular un reloj ahora', 'Jetzt eine Uhr verbinden', 'Connecter une montre maintenant', 'Ligar um relógio agora')
_tr7('ob.step3.later', 'スキップ — あとでつなぐ', '跳过 — 稍后再连', 'Пропустить — подключу позже', 'Saltar: lo vinculo después', 'Überspringen — ich verbinde später', 'Passer — je connecterai plus tard', 'Saltar — ligo mais tarde')
_tr7('ob.step3.later_note', '今はいい？「次へ」を押すだけ — 時計は「ゲーム中 → 時計のつなぎ方」からいつでもつなげる。', '现在不想连？直接点“下一步”— 随时可以在“游戏中 → 如何连接手表”里配对。', 'Не сейчас? Просто нажми «Далее» — подключить часы можно когда угодно в «В игре → Как подключить часы».', '¿Ahora no? Pulsa Siguiente: puedes vincularlo cuando quieras en «En el juego → Cómo vincular un reloj».', 'Jetzt nicht? Klick einfach auf Weiter — verbinden kannst du jederzeit unter „Im Spiel → Uhr verbinden“.', 'Pas maintenant ? Clique sur Suivant — tu peux connecter à tout moment dans « En jeu → Connecter une montre ».', 'Agora não? Carrega em Seguinte — podes ligar quando quiseres em «No jogo → Como ligar um relógio».')
_tr7('ob.step4.title', '見た目を選んで、入る', '选个外观，进去吧', 'Выбери вид и заходи', 'Elige un aspecto y entra', 'Look wählen und loslegen', 'Choisis un look et entre', 'Escolhe um visual e entra')
_tr7('ob.step4.body', '色はあとから設定でいつでも変えられる。', '颜色随时可以在设置里改。', 'Цвета можно в любой момент поменять в настройках.', 'Puedes cambiar los colores cuando quieras en Ajustes.', 'Die Farben kannst du jederzeit in den Einstellungen ändern.', 'Tu peux changer les couleurs à tout moment dans les réglages.', 'Podes mudar as cores quando quiseres nas Definições.')
_tr7('onboarding.confirm', '完了 — 開始', '完成 — 开始', 'Готово — запустить', 'Listo: empezar', 'Fertig — starten', 'Terminé — démarrer', 'Pronto — iniciar')
_tr7('onboarding.zen.title', '墨 Sumi — 墨', '墨 Sumi — 墨色', '墨 Sumi — тушь', '墨 Sumi — tinta', '墨 Sumi — Tusche', '墨 Sumi — encre', '墨 Sumi — tinta')
_tr7('onboarding.zen.desc', '温かみのある墨の黒に金のアクセント。\n青がきつい夜のセッション向け。', '温暖的墨黑配金色点缀。\n适合蓝光太刺眼的夜间时段。', 'Тёплая чернильная чернота с золотым акцентом.\nДля ночных сессий, когда синего слишком много.', 'Negro tinta cálido con acento dorado.\nPara sesiones nocturnas cuando el azul cansa.', 'Warmes Tuscheschwarz mit Goldakzent.\nFür Nachtsessions, wenn Blau zu viel ist.', 'Noir d’encre chaud avec un accent doré.\nPour les sessions nocturnes quand le bleu fatigue.', 'Preto de tinta quente com um toque dourado.\nPara sessões noturnas quando o azul cansa.')
_tr7('onboarding.modern.desc', '墨の上に藍の道着のブルー。\n「ダークモード」ではなく、武道の静けさ。', '墨色之上的靛蓝道服色。\n是武道的沉静，不是“深色模式”。', 'Индиговая синева доги поверх туши.\nСпокойствие боевых искусств, а не «тёмная тема».', 'Azul índigo de dōgi sobre tinta.\nCalma marcial, no un «modo oscuro».', 'Indigoblaues Dōgi über Tusche.\nKampfkunst-Ruhe, kein „Dark Mode“.', 'Bleu indigo du dōgi sur l’encre.\nLe calme martial, pas un « mode sombre ».', 'Azul índigo do dōgi sobre tinta.\nCalma marcial, não um «modo escuro».')
_tr7('safety.title', 'アンチチートに対してなぜ安全なのか', '为什么这对反作弊是安全的', 'Почему это безопасно для анти-чита', 'Por qué esto es seguro con el anti-cheat', 'Warum das Anti-Cheat-sicher ist', 'Pourquoi c’est sans risque pour l’anti-triche', 'Porque é que isto é seguro com o anti-cheat')
_tr7('safety.body', 'アプリは自前の透明なウィンドウを描くだけ。ゲームのプロセスに入らず、描画をフックせず、ゲームのメモリや画面の中身を読まない。ウィンドウはクリックもフォーカスも受け取らず、Alt+Tab にも出ない。スクリーンショットや OBS からは意図的に隠れない — 隠れるのはチート用オーバーレイのやることだから。', '应用只绘制自己的透明窗口，仅此而已。它不进入游戏进程、不挂钩渲染、不读取游戏内存或屏幕内容。该窗口不接收点击和焦点，也不出现在 Alt+Tab 中。它刻意不对截图或 OBS 隐藏 — 那是作弊覆盖层才会做的事。', 'Приложение рисует собственное прозрачное окно и больше ничего. Оно не входит в процесс игры, не перехватывает рендеринг, не читает память игры и содержимое экрана. Окно не принимает клики и фокус и не появляется в Alt+Tab. Оно намеренно не прячется от скриншотов и OBS — именно так поступают читерские оверлеи.', 'La app dibuja su propia ventana transparente y nada más. Nunca entra en el proceso del juego, no engancha el renderizado ni lee la memoria del juego o el contenido de la pantalla. La ventana no recibe clics ni foco y se mantiene fuera de Alt+Tab. A propósito no se oculta de las capturas ni de OBS: eso es lo que hacen los overlays tramposos.', 'Die App zeichnet ihr eigenes transparentes Fenster und sonst nichts. Sie betritt nie den Spielprozess, hookt kein Rendering, liest weder Spielspeicher noch Bildschirminhalte. Das Fenster nimmt weder Klicks noch Fokus an und bleibt aus Alt+Tab heraus. Es versteckt sich bewusst nicht vor Screenshots oder OBS — genau das tun Cheat-Overlays.', 'L’app dessine sa propre fenêtre transparente, et rien d’autre. Elle n’entre jamais dans le processus du jeu, n’accroche pas le rendu, ne lit ni la mémoire du jeu ni le contenu de l’écran. La fenêtre ne prend ni clics ni focus et reste hors de l’Alt+Tab. Elle ne se cache délibérément pas des captures d’écran ni d’OBS — c’est précisément ce que font les overlays de triche.', 'O app desenha a sua própria janela transparente e nada mais. Nunca entra no processo do jogo, não faz hook do rendering, não lê memória do jogo nem o conteúdo do ecrã. A janela não recebe cliques nem foco e fica fora do Alt+Tab. Deliberadamente não se esconde de capturas de ecrã nem do OBS — é isso que os overlays de batota fazem.')
_tr7('slot.file_short', 'ファイル', '文件', 'Файл', 'Archivo', 'Datei', 'Fichier', 'Ficheiro')
_tr7('slot.record_short', '録音', '录音', 'Запись', 'Grabar', 'Aufnehmen', 'Enregistrer', 'Gravar')
_tr7('slots.title', 'アプリが言うこと', '应用会说什么', 'Что говорит приложение', 'Lo que dice la app', 'Was die App sagt', 'Ce que dit l’app', 'O que a app diz')
_tr7('slots.hint', 'いつ言うかは体が決める — 負荷がしばらく高いままなら、次の休みに声をかける。ここでは何を言うかを決める。「音声＋効果音」は両方鳴らす。', '什么时候开口由你的身体决定 — 负荷持续偏高后，应用会在下一次停顿时提醒你。这里设置它具体说什么。“语音 + 音效”会同时播放两者。', 'Когда сказать, решает твоё тело — приложение ждёт, пока нагрузка подержится, и говорит в ближайшей паузе. Здесь ты задаёшь, что именно. «Голос + звук» проигрывает и то, и другое.', 'Cuándo habla lo decide tu cuerpo: la app espera a que la carga se mantenga y habla en la siguiente pausa. Aquí defines qué dice. «Voz + sonido» reproduce ambos.', 'Wann sie spricht, entscheidet dein Körper — die App wartet, bis die Last eine Weile oben bleibt, und spricht in der nächsten Pause. Hier legst du fest, was sie sagt. „Stimme + Ton“ spielt beides.', 'Quand elle parle, c’est ton corps qui décide — l’app attend que la charge tienne un moment, puis parle à la prochaine pause. Ici tu choisis quoi. « Voix + son » joue les deux.', 'Quando fala é o teu corpo que decide — a app espera que a carga se mantenha e fala na pausa seguinte. Aqui defines o quê. «Voz + som» toca ambos.')
_tr7('slots.clear_selection', '選択を解除', '取消选择', 'Снять выделение', 'Quitar selección', 'Auswahl aufheben', 'Annuler la sélection', 'Limpar seleção')
_tr7('slots.remove_selected', '選択したものを削除', '删除所选', 'Удалить выбранные', 'Eliminar seleccionados', 'Ausgewählte entfernen', 'Supprimer la sélection', 'Remover selecionados')
_tr7('slots.selected_count', '選択中: {n}', '已选：{n}', 'Выбрано: {n}', 'Seleccionados: {n}', 'Ausgewählt: {n}', 'Sélectionnés : {n}', 'Selecionados: {n}')
_tr7('slots.remove_confirm', '選択した {n} 個のトリガーを削除する？\n\n{list}', '删除所选的 {n} 个触发器？\n\n{list}', 'Удалить {n} выбранных триггеров?\n\n{list}', '¿Eliminar los {n} disparadores seleccionados?\n\n{list}', '{n} ausgewählte Trigger entfernen?\n\n{list}', 'Supprimer les {n} déclencheurs sélectionnés ?\n\n{list}', 'Remover os {n} gatilhos selecionados?\n\n{list}')
_tr7('dashboard.stats_title', 'マイ統計', '我的统计', 'Моя статистика', 'Mis estadísticas', 'Meine Statistiken', 'Mes statistiques', 'As minhas estatísticas')
_tr7('dashboard.edit_stats', '✎ 編集', '✎ 编辑', '✎ изменить', '✎ editar', '✎ bearbeiten', '✎ modifier', '✎ editar')
_tr7('dashboard.picker_title', '表示したいもの', '你想看到什么', 'Что показывать', 'Qué quieres ver', 'Was du sehen willst', 'Ce que tu veux voir', 'O que queres ver')
_tr7('dashboard.unit.hrr', '1分あたりの BPM', '每分钟 BPM', 'BPM за минуту', 'BPM por minuto', 'BPM pro Minute', 'BPM par minute', 'BPM por minuto')
_tr7('dashboard.unit.over', 'このセッション', '本次记录', 'за эту сессию', 'esta sesión', 'diese Sitzung', 'cette séance', 'esta sessão')
_tr7('dashboard.unit.avg', 'このセッション', '本次记录', 'за эту сессию', 'esta sesión', 'diese Sitzung', 'cette séance', 'esta sessão')
_tr7('dashboard.unit.breath', '自動', '自动', 'автоматически', 'automático', 'automatisch', 'automatique', 'automático')
_tr7('dashboard.unit.max', '今日のピーク', '今日峰值', 'пик за сегодня', 'pico de hoy', 'Höchstwert heute', 'pic du jour', 'pico de hoje')
_tr7('dashboard.unit.peak', '0〜100 のうち', '满分 100', 'из 0–100', 'de 0–100', 'von 0–100', 'sur 0–100', 'de 0–100')
_tr7('dnes.hr_title', '心拍と負荷', '心率与负荷', 'Пульс и нагрузка', 'Pulso y carga', 'Puls und Last', 'Pouls et charge', 'Pulso e carga')
_tr7('dnes.bpm_unit', '1分あたりの拍数', '每分钟心跳', 'ударов в минуту', 'latidos por minuto', 'Schläge pro Minute', 'battements par minute', 'batimentos por minuto')
_tr7('dnes.hr_connected', '時計に接続済み', '手表已连接', 'часы подключены', 'reloj conectado', 'Uhr verbunden', 'montre connectée', 'relógio ligado')
_tr7('dnes.hr_waiting', '時計を待っています', '等待手表', 'жду часы', 'esperando al reloj', 'warte auf die Uhr', 'en attente de la montre', 'à espera do relógio')
_tr7('dnes.empty_title', 'ここに心拍が出ます', '你的心率会显示在这里', 'Здесь появится твой пульс', 'Aquí aparecerá tu pulso', 'Hier erscheint dein Puls', 'Ton pouls apparaîtra ici', 'O teu pulso aparece aqui')
_tr7('dnes.empty_body', '時計をつなぐと、アプリがここに心拍と負荷を描き、必要なときには自分で呼吸を出してくれる。', '连接手表后，应用会在这里画出你的心率和负荷，并在需要时自动启动呼吸。', 'Как только подключишь часы, приложение начнёт рисовать здесь пульс и нагрузку и само запустит дыхание, когда понадобится.', 'En cuanto vincules el reloj, la app dibujará aquí tu pulso y tu carga, y lanzará la respiración sola cuando haga falta.', 'Sobald du deine Uhr verbindest, zeichnet die App hier Puls und Last und startet die Atmung bei Bedarf von selbst.', 'Dès que tu connectes ta montre, l’app dessine ici ton pouls et ta charge et lance la respiration d’elle-même au besoin.', 'Assim que ligares o relógio, o app desenha aqui o teu pulso e a carga e inicia a respiração sozinho quando for preciso.')
_tr7('dnes.empty_btn', '時計をつなぐ', '连接手表', 'Подключить часы', 'Vincular el reloj', 'Uhr verbinden', 'Connecter la montre', 'Ligar o relógio')
_tr7('dnes.trace_title', 'セッションの軌跡', '本次轨迹', 'След сессии', 'Rastro de la sesión', 'Spur der Sitzung', 'Trace de la séance', 'Rasto da sessão')
_tr7('dnes.trace_meta', '{time} · 呼吸 {n} 回', '{time} · 呼吸 {n} 次', '{time} · дыхание {n}×', '{time} · respiración {n}×', '{time} · Atmung {n}×', '{time} · respiration {n}×', '{time} · respiração {n}×')
_tr7('dnes.zones_title', 'セッションの内訳', '这次都在哪个区间', 'Где прошла сессия', 'Dónde fue la sesión', 'Wo die Sitzung lag', 'Où la séance s’est passée', 'Onde a sessão passou')
_tr7('dnes.zones_hint', 'セッションのうち、どの帯にどれだけいたか。帯は自分の安静時ベースラインを基準に測る — 表の数値ではない。', '本次记录中你在各区间待了多久。区间以你自己的静息基线为准，而不是表格数值。', 'Сколько времени за сессию ты провёл в каждой зоне. Зоны считаются от твоей собственной базовой линии покоя, а не от табличного значения.', 'Cuánto de la sesión pasaste en cada zona. Las zonas se miden frente a tu propia línea base en reposo, no frente a un valor de tabla.', 'Wie viel der Sitzung du in welcher Zone verbracht hast. Die Zonen messen gegen deine eigene Ruhebasislinie, nicht gegen einen Tabellenwert.', 'Combien de la séance tu as passé dans chaque zone. Les zones se mesurent par rapport à ta propre ligne de base au repos, pas à une valeur de table.', 'Quanto da sessão passaste em cada zona. As zonas medem-se face à tua própria linha de base em repouso, não a um valor de tabela.')
_tr7('dnes.session_title', 'このセッション', '本次记录', 'Эта сессия', 'Esta sesión', 'Diese Sitzung', 'Cette séance', 'Esta sessão')
_tr7('dnes.stat_min', '最低', '最低', 'Минимум', 'Mínimo', 'Tiefstwert', 'Minimum', 'Mínimo')
_tr7('dnes.stat_avg', '平均', '平均', 'Среднее', 'Media', 'Durchschnitt', 'Moyenne', 'Média')
_tr7('dnes.stat_max', '最高', '最高', 'Максимум', 'Máximo', 'Höchstwert', 'Maximum', 'Máximo')
_tr7('dnes.stat_over', 'しきい値超え', '超过阈值', 'Выше порога', 'Por encima del límite', 'Über der Grenze', 'Au-dessus du seuil', 'Acima do limite')
_tr7('dnes.stat_triggers', '呼吸サークルの発動', '呼吸圈触发', 'Круг дыхания сработал', 'Círculo de respiración lanzado', 'Atemkreis ausgelöst', 'Cercle de respiration déclenché', 'Círculo de respiração disparado')
_tr7('dnes.stat_hrr', '心拍回復（HRR）', '心率恢复（HRR）', 'Восстановление пульса (HRR)', 'Recuperación del pulso (HRR)', 'Herzfrequenz-Erholung (HRR)', 'Récupération cardiaque (HRR)', 'Recuperação do pulso (HRR)')
_tr7('dnes.load_note', '心拍から、自分の安静時ベースラインを基準に算出。これは HRV ではない — 時計が送るのは1分あたりの拍数であって、拍と拍の間隔ではない。', '由心率相对你自己的静息基线推算而来。这不是 HRV — 手表发送的是每分钟心跳数，而不是心跳间隔。', 'Выводится из пульса относительно твоей собственной базовой линии покоя. Это не HRV — часы присылают удары в минуту, а не промежутки между ударами.', 'Se deriva del pulso frente a tu propia línea base en reposo. Esto no es HRV: el reloj envía latidos por minuto, no los intervalos entre latidos.', 'Abgeleitet aus dem Puls gegenüber deiner eigenen Ruhebasislinie. Das ist kein HRV — die Uhr sendet Schläge pro Minute, nicht die Abstände dazwischen.', 'Dérivé du pouls par rapport à ta propre ligne de base au repos. Ce n’est pas la VFC — la montre envoie des battements par minute, pas les intervalles entre eux.', 'Derivado do pulso face à tua própria linha de base em repouso. Isto não é HRV — o relógio envia batimentos por minuto, não os intervalos entre eles.')
_tr7('dnes.why_line', 'ゲーム中、気づく前に体はこわばる — Zanshin はそこに短いリセットを結びつける。', '游戏中身体在你察觉前就绷紧了 — Zanshin 把一次短暂的重置绑在那一刻。', 'В игре тело напрягается раньше, чем ты заметишь, — Zanshin привязывает к этому короткий сброс.', 'En plena partida el cuerpo se tensa antes de que lo notes: Zanshin ata un reinicio corto a ese momento.', 'Mitten im Spiel verspannt sich der Körper, bevor du es merkst — Zanshin knüpft daran einen kurzen Reset.', 'En pleine partie, le corps se crispe avant que tu le remarques — Zanshin y attache une remise à zéro courte.', 'A meio do jogo o corpo tensiona antes de repares — o Zanshin liga a isso um reset curto.')
_tr7('dnes.why_link', '科学的な背景 →', '背后的科学 →', 'Наука за этим →', 'La ciencia detrás →', 'Die Wissenschaft dahinter →', 'La science derrière →', 'A ciência por trás →')
_tr7('tour.next', '次へ', '下一步', 'Далее', 'Siguiente', 'Weiter', 'Suivant', 'Seguinte')
_tr7('tour.skip', 'スキップ', '跳过', 'Пропустить', 'Saltar', 'Überspringen', 'Passer', 'Saltar')
_tr7('tour.done_btn', 'わかった', '知道了', 'Понятно', 'Entendido', 'Alles klar', 'Compris', 'Entendido')
_tr7('tour.step_of', 'ステップ {n} / {total}', '第 {n} 步，共 {total} 步', 'ШАГ {n} из {total}', 'PASO {n} de {total}', 'SCHRITT {n} von {total}', 'ÉTAPE {n} sur {total}', 'PASSO {n} de {total}')
_tr7('tour.welcome.title', 'かんたんツアー', '快速导览', 'Быстрая экскурсия', 'Recorrido rápido', 'Kurze Tour', 'Visite rapide', 'Visita rápida')
_tr7('tour.welcome.body', 'どこに何があるか案内する — 数秒で終わる。いつでもスキップできる。', '带你看看东西都在哪儿 — 只要几秒。随时可以跳过。', 'Покажу, где что находится — это пара секунд. Пропустить можно в любой момент.', 'Te enseño dónde está cada cosa: son unos segundos. Puedes saltarlo cuando quieras.', 'Ich zeige dir, wo was ist — dauert ein paar Sekunden. Du kannst jederzeit überspringen.', 'Je te montre où se trouve quoi — quelques secondes. Tu peux passer à tout moment.', 'Mostro-te onde está o quê — são uns segundos. Podes saltar quando quiseres.')
_tr7('tour.kamae.title', '開始と停止', '开始与停止', 'Запуск и остановка', 'Iniciar y detener', 'Starten und stoppen', 'Démarrer et arrêter', 'Iniciar e parar')
_tr7('tour.triggers.title', 'トリガー', '触发器', 'Триггеры', 'Disparadores', 'Trigger', 'Déclencheurs', 'Gatilhos')
_tr7('tour.sound.title', 'サウンド', '声音', 'Звук', 'Sonido', 'Ton', 'Son', 'Som')
_tr7('tour.sound.body', '合図の音声と効果音。声も音量も選べるし、自分で録音したものも使える。', '提示的语音和音效。可以选声音、音量，也能用你自己的录音。', 'Голос и звуковые эффекты подсказок. Можно выбрать голос, громкость и даже свои записи.', 'La voz y los efectos de sonido de los avisos. Puedes elegir voz, volumen e incluso tus propias grabaciones.', 'Stimme und Soundeffekte der Hinweise. Du kannst Stimme, Lautstärke und sogar eigene Aufnahmen wählen.', 'La voix et les effets sonores des repères. Tu peux choisir la voix, le volume et même tes propres enregistrements.', 'A voz e os efeitos sonoros dos avisos. Podes escolher voz, volume e até as tuas próprias gravações.')
_tr7('tour.ingame.title', 'ゲーム中', '游戏中', 'В игре', 'En el juego', 'Im Spiel', 'En jeu', 'No jogo')
_tr7('tour.ingame.body', 'プレイ中にアプリが描くものすべて — アイコン、心拍の HUD — と時計のペアリング。アイコンの位置はここで自由に動かせる。', '游戏时应用绘制的一切 — 图标、心率 HUD — 以及手表配对。图标位置在这里随意拖动。', 'Всё, что приложение рисует во время игры — значки, HUD с пульсом — и подключение часов. Значки перетаскиваешь куда хочешь именно здесь.', 'Todo lo que la app dibuja mientras juegas —iconos, el HUD del pulso— y la vinculación del reloj. Aquí arrastras los iconos donde quieras.', 'Alles, was die App beim Spielen zeichnet — Symbole, das Puls-HUD — und die Uhr-Verbindung. Die Symbole ziehst du hier hin, wo du willst.', 'Tout ce que l’app dessine pendant que tu joues — icônes, HUD du pouls — et la connexion de la montre. C’est ici que tu déplaces les icônes.', 'Tudo o que o app desenha enquanto jogas — ícones, o HUD do pulso — e a ligação do relógio. É aqui que arrastas os ícones para onde quiseres.')
_tr7('tour.sensor.title', '時計と心拍', '手表与心率', 'Часы и пульс', 'Reloj y pulso', 'Uhr und Puls', 'Montre et pouls', 'Relógio e pulso')
_tr7('tour.sensor.body', 'ここでアプリにどこで待ち受けるかを教える。心拍を渡せば、自分では絶対に思い出さないタイミングで呼吸サークルを自分で出してくれる。時計がなくても他はすべて同じように動く。', '在这里告诉应用该在哪里监听。把心率交给它，它就会在你绝对想不起来的那一刻自己启动呼吸圈。没有手表，其他一切照常。', 'Здесь ты говоришь приложению, где слушать. Дай ему свой пульс — и круг дыхания запустится сам ровно тогда, когда ты бы о нём не подумал. Без часов всё остальное работает так же.', 'Aquí le dices a la app dónde escuchar. Dale tu pulso y arrancará el círculo de respiración sola, justo cuando no se te ocurriría. Sin reloj, todo lo demás funciona igual.', 'Hier sagst du der App, wo sie lauschen soll. Gib ihr deinen Puls und sie startet den Atemkreis von selbst — genau dann, wenn du nicht daran denken würdest. Ohne Uhr funktioniert alles andere genauso.', 'Ici tu dis à l’app où écouter. Donne-lui ton pouls et elle lance le cercle de respiration d’elle-même, exactement quand tu n’y penserais pas. Sans montre, tout le reste fonctionne pareil.', 'Aqui dizes ao app onde ouvir. Dá-lhe o teu pulso e ele inicia o círculo de respiração sozinho — exatamente quando não te lembrarias. Sem relógio, tudo o resto funciona igual.')
_tr7('tour.today.title', '心拍から見えるもの', '从心率里能看到什么', 'Что видно по пульсу', 'Qué ves desde tu pulso', 'Was du vom Puls siehst', 'Ce que tu vois de ton pouls', 'O que vês do teu pulso')
_tr7('tour.today.body', 'セッションの軌跡は一晩まるごとを一度に見せる — どこで心拍が跳ね、どれだけ続いたか。隣にはどの帯にどれだけいたかが出る。上のカードは自分の見たいものに入れ替えられる。', '轨迹把整晚一次看完 — 心率在哪里飙升、又持续了多久。旁边显示你在各区间待了多久。上面的卡片可以换成你关心的指标。', 'След сессии показывает весь вечер сразу — где пульс подскочил и как долго держался. Рядом видно, сколько времени ты провёл в каждой зоне. Карточки сверху можно заменить на те, что тебя интересуют.', 'El rastro muestra la velada entera de una vez: dónde se disparó el pulso y cuánto se mantuvo. Al lado ves cuánto tiempo pasaste en cada zona. Las tarjetas de arriba se pueden cambiar por las que te interesen.', 'Die Spur zeigt den ganzen Abend auf einmal — wo der Puls hochging und wie lange er blieb. Daneben siehst du, wie viel Zeit du in welcher Zone verbracht hast. Die Karten oben lassen sich gegen die tauschen, die dich interessieren.', 'La trace montre toute la soirée d’un coup — où le pouls a bondi et combien de temps il est resté. À côté, tu vois le temps passé dans chaque zone. Les cartes du haut se remplacent par celles qui t’intéressent.', 'O rasto mostra a noite inteira de uma vez — onde o pulso disparou e quanto tempo ficou. Ao lado vês quanto tempo passaste em cada zona. Os cartões de cima podem ser trocados pelos que te interessam.')
_tr7('tour.history.title', 'セッション履歴', '记录历史', 'История сессий', 'Historial de sesiones', 'Sitzungsverlauf', 'Historique des séances', 'Histórico de sessões')
_tr7('tour.history.body', '何回かセッションを重ねると、ここに推移が出る — 安静時ベースライン、心拍回復、そして遊んだ日のグリッド。行をクリックすれば、どのセッションもじっくり見られる。', '几次记录之后，这里会显示趋势 — 静息基线、心率恢复，以及你游玩日期的格子图。点击某一行就能细看那一次。', 'После нескольких сессий здесь появится динамика — базовая линия покоя, восстановление пульса и сетка дней, когда ты играл. Клик по строке открывает любую сессию вблизи.', 'Tras unas cuantas sesiones verás aquí la evolución: línea base en reposo, recuperación del pulso y una cuadrícula de los días que jugaste. Haz clic en una fila para ver cualquier sesión de cerca.', 'Nach ein paar Sitzungen siehst du hier den Verlauf — Ruhebasislinie, Herzfrequenz-Erholung und ein Raster der Tage, an denen du gespielt hast. Ein Klick auf eine Zeile zeigt jede Sitzung aus der Nähe.', 'Après quelques séances, tu verras ici l’évolution — ligne de base au repos, récupération cardiaque et une grille des jours joués. Clique sur une ligne pour voir une séance de près.', 'Ao fim de algumas sessões vês aqui a evolução — linha de base em repouso, recuperação do pulso e uma grelha dos dias em que jogaste. Clica numa linha para ver qualquer sessão de perto.')
_tr7('tour.guide.title', 'ガイド', '指南', 'Справочник', 'Guía', 'Leitfaden', 'Guide', 'Guia')
_tr7('tour.guide.body', 'なぜ効くのか — 各合図の短い説明と、その裏にある科学。', '为什么有效 — 每个提示的简短说明和背后的科学。', 'Почему это работает — короткое объяснение каждой подсказки и наука за ней.', 'Por qué funciona: una explicación breve de cada aviso y la ciencia detrás.', 'Warum es wirkt — eine kurze Erklärung zu jedem Hinweis und die Wissenschaft dahinter.', 'Pourquoi ça marche — une brève explication de chaque repère et la science derrière.', 'Porque funciona — uma explicação curta de cada aviso e a ciência por trás.')
_tr7('tour.dock.title', '開始と停止', '开始与停止', 'Запуск и остановка', 'Iniciar y detener', 'Starten und stoppen', 'Démarrer et arrêter', 'Iniciar e parar')
_tr7('tour.done.title', 'これで終わり', '就这些', 'Вот и всё', 'Eso es todo', 'Das war’s', 'C’est tout', 'É tudo')
_tr7('tour.kamae.body', 'このバーが主スイッチです。左の ▶ / ▮▮ ボタンでアプリを開始・停止します。監視中はバーがゆっくり呼吸し、停止中は静かです。', '这条横条是主开关。左边的 ▶ / ▮▮ 按钮用来启动和停止应用。监听时横条会缓缓呼吸，停止时保持安静。', 'Эта полоса — главный переключатель. Кнопка ▶ / ▮▮ слева запускает и останавливает приложение. Когда оно слушает, полоса мягко дышит; когда стоит — спокойна.', 'Esta barra es el interruptor principal. El botón ▶ / ▮▮ de la izquierda inicia y detiene la app. Mientras escucha, la barra respira suavemente; parada, está quieta.', 'Diese Leiste ist der Hauptschalter. Der Knopf ▶ / ▮▮ links startet und stoppt die App. Während sie zuhört, atmet die Leiste sanft; gestoppt ist sie ruhig.', 'Cette barre est l’interrupteur principal. Le bouton ▶ / ▮▮ à gauche démarre et arrête l’app. Quand elle écoute, la barre respire doucement ; à l’arrêt, elle est immobile.', 'Esta barra é o interruptor principal. O botão ▶ / ▮▮ à esquerda inicia e para a app. Enquanto ouve, a barra respira devagar; parada, fica quieta.')
_tr7('tour.dock.body', 'これは円相（ensō）— アプリの印であり状態でもあります。緑で呼吸していれば監視中、赤で静止していれば停止中。体が高いままだと内側にゆっくりした環が現れ、いい頃合いを待っている合図です。円相はこのページにあり、他のページでは左の帯の色つきの点が状態を示します。', '这是圆相（ensō）—— 既是应用的标志，也是它的状态。绿色并在呼吸表示正在监听；红色且静止表示已停止。当身体持续紧绷时，内部会出现一个缓慢的环，表示应用正在等待合适的时机。它只在本页；在其他页面，左侧栏的彩色圆点表示状态。', 'Это энсо — знак приложения и его состояние одновременно. Зелёное и дышащее — слушает; красное и неподвижное — остановлено. Когда тело долго держится на взводе, внутри появляется медленное кольцо: приложение ждёт подходящего момента. Энсо живёт на этой странице; на остальных состояние показывает цветная точка в левой панели.', 'Esto es el ensō: la marca de la app y su estado a la vez. Verde y respirando significa que escucha; rojo e inmóvil, que está detenida. Cuando el cuerpo se mantiene tenso, aparece dentro un anillo lento: la app espera un buen momento. Vive en esta página; en las demás, el punto de color de la barra izquierda lleva el estado.', 'Das ist das Ensō — Zeichen der App und ihr Zustand zugleich. Grün und atmend heißt, sie hört zu; rot und still heißt, sie ist gestoppt. Bleibt dein Körper oben, erscheint darin ein langsamer Ring: die App wartet auf einen guten Moment. Es lebt auf dieser Seite; auf den anderen trägt der farbige Punkt in der linken Leiste den Zustand.', 'Voici l’ensō — la marque de l’app et son état à la fois. Vert et respirant : elle écoute ; rouge et immobile : elle est arrêtée. Quand ton corps reste tendu, un anneau lent apparaît à l’intérieur : l’app attend le bon moment. Il vit sur cette page ; ailleurs, le point coloré de la barre de gauche porte l’état.', 'Isto é o ensō — a marca da app e o seu estado ao mesmo tempo. Verde e a respirar significa que está a ouvir; vermelho e imóvel, que está parada. Quando o corpo se mantém em tensão, aparece lá dentro um anel lento: a app está à espera de um bom momento. Vive nesta página; nas outras, o ponto colorido da barra esquerda leva o estado.')
_tr7('tour.done.body', 'このツアーは設定からいつでもやり直せる。よいゲームを。', '这个导览随时可以在设置里重看。玩得开心。', 'Эту экскурсию можно повторить в настройках когда угодно. Хорошей игры.', 'Puedes repetir este recorrido cuando quieras en Ajustes. Que disfrutes la partida.', 'Diese Tour kannst du jederzeit in den Einstellungen wiederholen. Viel Spaß beim Spielen.', 'Tu peux rejouer cette visite à tout moment dans les réglages. Bon jeu.', 'Podes repetir esta visita quando quiseres nas Definições. Bom jogo.')
_tr7('metric.bpm.title', '現在の心拍', '当前心率', 'Пульс сейчас', 'Pulso ahora', 'Puls jetzt', 'Pouls actuel', 'Pulso agora')
_tr7('metric.bpm.short', '今、心臓が1分間に何回打っているか。', '你的心脏此刻每分钟跳多少下。', 'Сколько раз в минуту сейчас бьётся твоё сердце.', 'Cuántas veces por minuto late ahora tu corazón.', 'Wie oft dein Herz gerade pro Minute schlägt.', 'Combien de fois par minute ton cœur bat en ce moment.', 'Quantas vezes por minuto o teu coração bate agora.')
_tr7('metric.bpm.more', '基本の数字。それ自体はあまり語らない — 大事なのは安静時の水準からどれだけ動くか、そして落ち着いたときにどれだけ速く下がるか。', '最基础的数字。单看它意义不大 — 重要的是它相对你的静息水平怎么动，以及你平静下来时下降得多快。', 'Базовое число. Само по себе оно мало что говорит — важно, как оно движется относительно твоего уровня покоя и как быстро падает, когда ты успокаиваешься.', 'El número base. Por sí solo dice poco: lo que importa es cómo se mueve frente a tu nivel de reposo y con qué rapidez baja cuando te calmas.', 'Die Grundzahl. Für sich allein sagt sie wenig — entscheidend ist, wie sie sich gegenüber deinem Ruheniveau bewegt und wie schnell sie fällt, wenn du runterkommst.', 'Le chiffre de base. Seul, il dit peu — ce qui compte, c’est comment il bouge par rapport à ton niveau de repos et à quelle vitesse il redescend quand tu te calmes.', 'O número base. Sozinho diz pouco — o que importa é como se move face ao teu nível de repouso e com que rapidez desce quando te acalmas.')
_tr7('metric.baseline.tag', '安静時', '静息', 'покой', 'reposo', 'Ruhe', 'repos', 'repouso')
_tr7('metric.hrr.tag', '回復', '恢复', 'восстановление', 'recuperación', 'Erholung', 'récupération', 'recuperação')
_tr7('metric.over.tag', '超過時間', '超限', 'выше порога', 'sobre límite', 'über Grenze', 'au-dessus', 'acima')
_tr7('metric.breath.tag', '呼吸', '呼吸', 'дыхание', 'respiración', 'Atmung', 'respiration', 'respiração')
_tr7('metric.avg.tag', '平均', '平均', 'средний', 'media', 'Schnitt', 'moyenne', 'média')
_tr7('metric.max.tag', '最高', '最高', 'максимум', 'máximo', 'Maximum', 'maximum', 'máximo')
_tr7('metric.peak.tag', '負荷ピーク', '负荷峰值', 'пик нагрузки', 'pico', 'Spitze', 'pic', 'pico')
_tr7('metric.week.tag', '今週', '本周', 'за неделю', 'esta semana', 'diese Woche', 'cette semaine', 'esta semana')
_tr7('metric.baseline.title', '安静時ベースライン', '静息基线', 'Базовая линия покоя', 'Línea base en reposo', 'Ruhebasislinie', 'Ligne de base au repos', 'Linha de base em repouso')
_tr7('metric.baseline.short', 'ゲームに押されていないときの、あなたの心拍。', '游戏没有给你压力时的心率。', 'Твой пульс, когда игра тебя никуда не гонит.', 'Tu pulso cuando el juego no te está exigiendo.', 'Dein Puls, wenn dich das Spiel nicht drängt.', 'Ton pouls quand le jeu ne te pousse pas.', 'O teu pulso quando o jogo não te pressiona.')
_tr7('metric.baseline.more', 'アプリは最も落ち着いた瞬間から算出する。日ごとに上がっていくなら、体が疲れているかストレスがあるのかもしれない — 必ずしもゲームのせいではない（睡眠、カフェイン、体調）。だから一つの数字ではなく、時間の流れで追う。', '应用从你最平静的时刻推算。如果它一天天升高，可能是身体疲惫或压力大 — 不一定是游戏造成的（睡眠、咖啡因、生病）。所以我们看的是长期走势，而不是单个数字。', 'Приложение выводит её из самых спокойных моментов. Если она растёт день за днём, тело может быть уставшим или в стрессе — не обязательно из-за игры (сон, кофеин, болезнь). Поэтому мы следим за ней во времени, а не по одному числу.', 'La app la deduce de tus momentos más tranquilos. Si sube día tras día, tu cuerpo puede estar cansado o estresado, no necesariamente por jugar (sueño, cafeína, enfermedad). Por eso la seguimos en el tiempo y no como un número suelto.', 'Die App leitet sie aus deinen ruhigsten Momenten ab. Steigt sie Tag für Tag, ist dein Körper vielleicht müde oder gestresst — nicht zwangsläufig vom Spielen (Schlaf, Koffein, Krankheit). Deshalb verfolgen wir sie über die Zeit, nicht als Einzelwert.', 'L’app la déduit de tes moments les plus calmes. Si elle monte jour après jour, ton corps est peut-être fatigué ou stressé — pas forcément à cause du jeu (sommeil, caféine, maladie). C’est pourquoi on la suit dans le temps, pas comme un chiffre isolé.', 'O app deduz da tua fase mais calma. Se sobe dia após dia, o corpo pode estar cansado ou em stress — não necessariamente por jogares (sono, cafeína, doença). Por isso seguimo-la ao longo do tempo, não como um número isolado.')
_tr7('metric.load.title', '負荷', '负荷', 'Нагрузка', 'Carga', 'Last', 'Charge', 'Carga')
_tr7('metric.load.short', '今どれだけゲームに押されているか — 心拍から。HRV ではない。', '游戏此刻给你多大压力 — 由心率得出，不是 HRV。', 'Насколько сильно игра давит на тебя прямо сейчас — из пульса, не из HRV.', 'Cuánto te está exigiendo el juego ahora mismo: del pulso, no de la HRV.', 'Wie stark dich das Spiel gerade fordert — aus dem Puls, nicht aus HRV.', 'À quel point le jeu te pousse en ce moment — d’après le pouls, pas la VFC.', 'Quanto o jogo te está a exigir agora — a partir do pulso, não da HRV.')
_tr7('metric.load.more', '心拍から実際にわかる三つを組み合わせている：安静時からどれだけ上か、どれだけ速く上がっているか、どれだけ長く高いままか。これは HRV ではない — HRV には拍と拍の間隔が必要で、時計はそれをこの形では送らない。', '它结合了心率真正能说明的三件事：比静息高多少、上升有多快、在高位停留多久。这不是 HRV — HRV 需要心跳间隔，而手表并不以这种方式发送。', 'Она складывается из трёх вещей, которые пульс действительно может сказать: насколько ты выше покоя, как быстро он растёт и как долго держится. Это не HRV — для него нужны интервалы между ударами, а часы их так не присылают.', 'Combina tres cosas que el pulso sí puede decir: cuánto estás por encima del reposo, con qué rapidez sube y cuánto tiempo se mantiene. No es HRV: eso requiere intervalos latido a latido, que el reloj no envía así.', 'Sie kombiniert drei Dinge, die der Puls wirklich sagen kann: wie weit über der Ruhe du bist, wie schnell er steigt und wie lange er oben bleibt. Es ist kein HRV — dafür bräuchte es Schlag-zu-Schlag-Intervalle, die die Uhr so nicht sendet.', 'Elle combine trois choses que le pouls peut réellement dire : de combien tu es au-dessus du repos, à quelle vitesse il monte et combien de temps il reste haut. Ce n’est pas la VFC — il faudrait les intervalles entre battements, que la montre n’envoie pas ainsi.', 'Combina três coisas que o pulso consegue mesmo dizer: quanto estás acima do repouso, com que rapidez sobe e quanto tempo fica alto. Não é HRV — isso exige intervalos batimento a batimento, que o relógio não envia assim.')
_tr7('metric.hrr.title', '心拍回復（HRR）', '心率恢复（HRR）', 'Восстановление пульса (HRR)', 'Recuperación del pulso (HRR)', 'Herzfrequenz-Erholung (HRR)', 'Récupération cardiaque (HRR)', 'Recuperação do pulso (HRR)')
_tr7('metric.hrr.short', '心拍が跳ね上がったあと、1分でどれだけ下がったか。', '心率飙升之后，一分钟内下降了多少。', 'На сколько упал пульс за минуту после скачка.', 'Cuánto bajó tu pulso en el minuto siguiente a un pico.', 'Um wie viel dein Puls in der Minute nach einem Ausschlag gefallen ist.', 'De combien ton pouls est redescendu dans la minute suivant un pic.', 'Quanto o teu pulso desceu no minuto a seguir a um pico.')
_tr7('metric.hrr.more', 'どれだけ速く落ち着けるかを測る。下がり幅が大きいほど、静けさに早く戻る。ふつうは1分あたり12〜23拍、鍛えている人は29以上。回復が速いほど体力と結びつき、トレーニングで良くなる。', '它衡量你平静下来的速度。下降幅度越大，回到平静越快。通常为每分钟 12–23 次，训练有素的人为 29 以上。恢复越快与体能越好相关，并且可以通过训练改善。', 'Она измеряет, как быстро ты можешь успокоиться. Чем больше падение, тем скорее возвращается покой. Обычно 12–23 удара в минуту, у тренированных 29 и больше. Быстрое восстановление связано с лучшей формой и улучшается тренировкой.', 'Mide lo rápido que puedes calmarte. Una caída mayor = vuelves antes a la calma. Normalmente 12–23 latidos por minuto; en personas entrenadas, 29 o más. Una recuperación más rápida va ligada a mejor forma física y mejora con el entrenamiento.', 'Sie misst, wie schnell du runterkommst. Ein größerer Abfall = früher wieder ruhig. Typisch 12–23 Schläge pro Minute, bei Trainierten 29 und mehr. Schnellere Erholung geht mit besserer Fitness einher und verbessert sich durch Training.', 'Elle mesure la vitesse à laquelle tu redescends. Une baisse plus forte = retour au calme plus tôt. Typiquement 12–23 battements par minute, 29 et plus chez les personnes entraînées. Une récupération plus rapide va de pair avec une meilleure condition physique et s’améliore à l’entraînement.', 'Mede a rapidez com que consegues acalmar. Uma queda maior = volta à calma mais cedo. Tipicamente 12–23 batimentos por minuto, em pessoas treinadas 29 ou mais. Recuperação mais rápida está ligada a melhor forma e melhora com treino.')
_tr7('metric.zones.title', 'しきい値超え / 帯ごとの時間', '超阈值时间 / 各区间时间', 'Время выше порога / по зонам', 'Tiempo sobre el límite / por zonas', 'Zeit über der Grenze / in Zonen', 'Temps au-dessus du seuil / par zones', 'Tempo acima do limite / por zonas')
_tr7('metric.zones.short', 'セッションのうち、心拍が高いまま過ごした割合。', '本次记录里你心率偏高的时间占多少。', 'Сколько времени за сессию ты провёл с высоким пульсом.', 'Cuánto de la sesión pasaste con el pulso alto.', 'Wie viel der Sitzung du mit hohem Puls verbracht hast.', 'Combien de la séance tu as passé avec un pouls élevé.', 'Quanto da sessão passaste com o pulso alto.')
_tr7('metric.zones.more', 'ヘッドショットのあとの短い跳ね上がりはふつう。しきい値超えが長いなら、ゲームが緊張を保たせているということ — まさにアプリが自分で出せる呼吸が効く場面。', '爆头之后的短暂飙升很正常。长时间超过阈值意味着游戏一直让你绷着 — 这正是应用能自动启动的呼吸最有用的时候。', 'Короткие всплески после хедшота — нормально. Долгое время выше порога значит, что игра держит тебя в напряжении, — и именно тогда помогает дыхание, которое приложение может запустить само.', 'Los picos cortos tras un headshot son normales. Mucho tiempo por encima del límite significa que el juego te mantiene tenso, justo cuando ayuda la respiración que la app puede lanzar sola.', 'Kurze Ausschläge nach einem Headshot sind normal. Lange Zeit über der Grenze heißt, das Spiel hält dich angespannt — genau dann hilft die Atmung, die die App von selbst starten kann.', 'Les pics courts après un headshot sont normaux. Beaucoup de temps au-dessus du seuil signifie que le jeu te garde tendu — c’est exactement là que la respiration que l’app peut lancer seule aide.', 'Picos curtos depois de um headshot são normais. Muito tempo acima do limite significa que o jogo te mantém tenso — é exatamente aí que ajuda a respiração que o app pode iniciar sozinho.')
_tr7('metric.zones.calm', '平静', '平静', 'покой', 'calma', 'ruhig', 'calme', 'calmo')
_tr7('metric.zones.raised', 'やや上昇', '略高', 'повышенная', 'elevada', 'erhöht', 'élevée', 'elevada')
_tr7('metric.zones.high', '高い', '偏高', 'высокая', 'alta', 'hoch', 'haute', 'alta')
_tr7('metric.zones.critical', '危険域', '临界', 'критическая', 'crítica', 'kritisch', 'critique', 'crítica')
_tr7('metric.hrpi.title', 'HRPI', 'HRPI', 'HRPI', 'HRPI', 'HRPI', 'HRPI', 'HRPI')
_tr7('metric.hrpi.short', '心拍がどれだけ高く、どれだけ長く続いたかを一つにまとめた数字。', '把心率有多高、持续多久合成一个数字。', 'Одно число, связывающее, насколько высоко и как долго шёл твой пульс.', 'Un número que une lo alto y lo largo que estuvo tu pulso.', 'Eine Zahl, die verbindet, wie hoch und wie lange dein Puls lief.', 'Un chiffre qui relie la hauteur et la durée de ton pouls.', 'Um número que junta o quão alto e quanto tempo o teu pulso esteve.')
_tr7('metric.hrpi.more', '値 k は、心拍が少なくとも k 秒のあいだ、少なくとも毎分 k 拍あったという意味。高さと長さを一つにまとめるので、二つのセッションを一目で比べられる。', '数值 k 表示你的心率至少达到每分钟 k 次，并持续至少 k 秒。它把高度和时长合为一体，让你一眼就能比较两次记录。', 'Значение k означает, что пульс был не ниже k ударов в минуту в течение не менее k секунд. Оно соединяет высоту и длительность, так что две сессии можно сравнить одним взглядом.', 'Un valor k significa que tu pulso estuvo al menos a k latidos por minuto durante al menos k segundos. Une altura y duración, así que puedes comparar dos sesiones de un vistazo.', 'Ein Wert k heißt: Dein Puls lag mindestens k Schläge pro Minute für mindestens k Sekunden. Er verbindet Höhe und Dauer, sodass du zwei Sitzungen auf einen Blick vergleichen kannst.', 'Une valeur k signifie que ton pouls était d’au moins k battements par minute pendant au moins k secondes. Elle joint hauteur et durée, si bien que tu compares deux séances d’un coup d’œil.', 'Um valor k significa que o teu pulso esteve a pelo menos k batimentos por minuto durante pelo menos k segundos. Junta altura e duração, por isso comparas duas sessões num relance.')
_tr7('metric.over.title', 'しきい値超えの時間', '超过阈值的时间', 'Время выше порога', 'Tiempo sobre el límite', 'Zeit über der Grenze', 'Temps au-dessus du seuil', 'Tempo acima do limite')
_tr7('metric.breath.title', '呼吸の発動', '呼吸已触发', 'Дыхание запущено', 'Respiración lanzada', 'Atmung ausgelöst', 'Respiration déclenchée', 'Respiração disparada')
_tr7('metric.breath.short', '心拍が高いときに、アプリが自分で呼吸サークルを出した回数。', '在心率偏高时，应用自动启动呼吸圈的次数。', 'Сколько раз приложение само запускало круг дыхания при высоком пульсе.', 'Cuántas veces la app lanzó sola el círculo de respiración con el pulso alto.', 'Wie oft die App den Atemkreis bei hohem Puls von selbst gestartet hat.', 'Combien de fois l’app a lancé seule le cercle de respiration à pouls élevé.', 'Quantas vezes o app iniciou sozinho o círculo de respiração com o pulso alto.')
_tr7('metric.breath.more', 'これは自動の発動だけを数える（心拍がしばらく高いまま） — 自分でキーを押して呼吸サークルを出した回数は入らない。吸う・吐くの長さ（秒）は「ゲーム中の表示」の呼吸スロットで設定できる — サイクルが短いほどストレス下で早く落ち着き、長いほど深い呼吸になる。', '这里只统计自动触发（心率持续偏高）— 不包括你自己按键启动呼吸圈的次数。吸气与呼气的秒数可以在“游戏中的视觉”里的呼吸槽设置 — 周期越短，压力下平静得越快；越长，呼吸越深。', 'Здесь считаются только автоматические запуски (пульс какое-то время держался высоко) — не те разы, когда ты сам запустил круг дыхания клавишей. Длину вдоха и выдоха (в секундах) можно задать в «Визуалы в игре» на слоте Дыхание — короткий цикл помогает быстрее успокоиться под стрессом, длинный ведёт к более глубокому дыханию.', 'Aquí solo cuentan los lanzamientos automáticos (pulso alto mantenido un rato), no las veces que lanzaste el círculo tú con una tecla. La duración de inhalar y exhalar (en segundos) se ajusta en «Visuales en el juego», en el slot de Respiración: un ciclo más corto calma antes bajo estrés, uno más largo lleva a respirar más hondo.', 'Hier zählen nur automatische Auslösungen (Puls blieb eine Weile hoch) — nicht die Male, in denen du den Atemkreis selbst per Taste gestartet hast. Die Länge von Ein- und Ausatmen (in Sekunden) stellst du unter „Visuals im Spiel“ beim Atem-Slot ein — ein kürzerer Zyklus beruhigt unter Stress schneller, ein längerer führt zu tieferem Atem.', 'Ici ne comptent que les déclenchements automatiques (pouls resté haut un moment) — pas les fois où tu as lancé le cercle toi-même avec une touche. La durée d’inspiration et d’expiration (en secondes) se règle dans « Visuels en jeu », sur le slot Souffle — un cycle plus court calme plus vite sous stress, un plus long mène à une respiration plus profonde.', 'Aqui contam só os disparos automáticos (pulso alto durante algum tempo) — não as vezes em que iniciaste o círculo com uma tecla. A duração de inspirar e expirar (em segundos) define-se em «Visuais no jogo», no slot da Respiração — um ciclo mais curto acalma mais depressa sob stress, um mais longo leva a respiração mais funda.')
_tr7('metric.avg.title', '今日の平均心拍', '今日平均心率', 'Средний пульс сегодня', 'Pulso medio de hoy', 'Durchschnittspuls heute', 'Pouls moyen aujourd’hui', 'Pulso médio hoje')
_tr7('metric.avg.short', '今日のセッション全体の平均心拍。', '今天整场记录的平均心率。', 'Твой средний пульс за всю сегодняшнюю сессию.', 'Tu pulso medio en toda la sesión de hoy.', 'Dein Durchschnittspuls über die gesamte heutige Sitzung.', 'Ton pouls moyen sur toute la séance du jour.', 'O teu pulso médio em toda a sessão de hoje.')
_tr7('metric.avg.more', 'セッション全体を一つの数字にしたもの — 日々の比較には安静時ベースラインのほうが役に立つ。あちらは最も落ち着いた瞬間だけを数えるから。', '把整场记录压成一个数字 — 但要做日常比较，静息基线更有用，因为它只统计你最平静的时刻。', 'Одно число на всю сессию — для сравнения день ко дню полезнее базовая линия покоя: она считает только самые спокойные моменты.', 'Un número para toda la sesión: para comparar día a día es más útil la línea base en reposo, porque solo cuenta tus momentos más tranquilos.', 'Eine Zahl für die ganze Sitzung — für den Vergleich von Tag zu Tag ist die Ruhebasislinie nützlicher, denn sie zählt nur deine ruhigsten Momente.', 'Un chiffre pour toute la séance — pour comparer d’un jour à l’autre, la ligne de base au repos est plus utile : elle ne compte que tes moments les plus calmes.', 'Um número para toda a sessão — para comparar dia a dia, a linha de base em repouso é mais útil, porque só conta os teus momentos mais calmos.')
_tr7('metric.max.title', '最高心拍', '最高心率', 'Самый высокий пульс', 'Pulso más alto', 'Höchster Puls', 'Pouls le plus haut', 'Pulso mais alto')
_tr7('metric.max.short', '今日アプリが記録した最も高い心拍。', '应用今天记录到的最高心率。', 'Самый высокий пульс, который приложение записало сегодня.', 'El pulso más alto que la app ha registrado hoy.', 'Der höchste Puls, den die App heute aufgezeichnet hat.', 'Le pouls le plus haut que l’app a enregistré aujourd’hui.', 'O pulso mais alto que o app registou hoje.')
_tr7('metric.max.more', '単発のピークはそれ自体ではあまり語らない — もっと大事なのは、そのあとどれだけ速く心拍が戻ったか（HRR）。', '单个峰值本身说明不了什么 — 更重要的是之后心率回落得多快（HRR）。', 'Один скачок сам по себе мало что говорит — важнее, как быстро пульс потом вернулся вниз (HRR).', 'Un pico aislado dice poco por sí solo: importa más lo rápido que bajó el pulso después (HRR).', 'Ein einzelner Ausschlag sagt für sich wenig — wichtiger ist, wie schnell der Puls danach wieder gefallen ist (HRR).', 'Un pic isolé dit peu en soi — ce qui compte davantage, c’est la vitesse à laquelle le pouls est redescendu ensuite (HRR).', 'Um pico isolado diz pouco por si — importa mais a rapidez com que o pulso desceu depois (HRR).')
_tr7('metric.peak.title', '負荷のピーク', '负荷峰值', 'Пик нагрузки', 'Pico de carga', 'Last-Spitze', 'Pic de charge', 'Pico de carga')
_tr7('metric.peak.short', '今日のセッション中の最高の負荷値（0〜100）。', '今天记录中的最高负荷值（0–100）。', 'Самое высокое значение нагрузки (0–100) за сегодняшнюю сессию.', 'El valor de carga más alto (0–100) durante la sesión de hoy.', 'Der höchste Lastwert (0–100) in der heutigen Sitzung.', 'La valeur de charge la plus haute (0–100) pendant la séance du jour.', 'O valor de carga mais alto (0–100) durante a sessão de hoje.')
_tr7('metric.peak.more', '負荷は心拍から三つを組み合わせる：安静時からどれだけ上か、どれだけ速く上がっているか、どれだけ長く高いままか。ピークはその組み合わせが最も高かった一瞬。', '负荷把心率的三件事合起来：比静息高多少、上升多快、在高位停留多久。峰值就是这个组合最高的那一刻。', 'Нагрузка соединяет три вещи из пульса: насколько ты выше покоя, как быстро он растёт и как долго держится. Пик — самый высокий момент этого сочетания.', 'La carga combina tres cosas del pulso: cuánto estás por encima del reposo, con qué rapidez sube y cuánto se mantiene. El pico es el momento más alto de esa combinación.', 'Die Last kombiniert drei Dinge aus dem Puls: wie weit über der Ruhe du bist, wie schnell er steigt und wie lange er oben bleibt. Die Spitze ist der höchste Moment dieser Kombination.', 'La charge combine trois éléments du pouls : de combien tu es au-dessus du repos, à quelle vitesse il monte et combien de temps il reste haut. Le pic est le moment le plus haut de cette combinaison.', 'A carga combina três coisas do pulso: quanto estás acima do repouso, com que rapidez sobe e quanto tempo fica alto. O pico é o momento mais alto dessa combinação.')
_tr7('metric.week.title', '今週のセッション', '本周记录数', 'Сессии на этой неделе', 'Sesiones esta semana', 'Sitzungen diese Woche', 'Séances cette semaine', 'Sessões esta semana')
_tr7('metric.week.short', '今週いくつセッションをこなし、合計でどれだけの時間だったか。', '你本周玩了多少次记录，总共多长时间。', 'Сколько сессий ты провёл на этой неделе и сколько это в сумме времени.', 'Cuántas sesiones has jugado esta semana y cuánto tiempo suman.', 'Wie viele Sitzungen du diese Woche gespielt hast und wie viel Zeit das insgesamt war.', 'Combien de séances tu as jouées cette semaine et combien de temps au total.', 'Quantas sessões jogaste esta semana e quanto tempo deu ao todo.')
_tr7('metric.week.more', '週は月曜からかぞえる。今週アプリが記録した量のざっくりした目安。', '一周从周一算起。这只是应用本周记录量的一个概览。', 'Неделя считается с понедельника. Это просто обзор того, сколько приложение записало за эту неделю.', 'La semana cuenta desde el lunes. Es solo un resumen de cuánto ha registrado la app esta semana.', 'Die Woche zählt ab Montag. Es ist nur ein Überblick, wie viel die App diese Woche aufgezeichnet hat.', 'La semaine compte à partir du lundi. C’est juste un aperçu de ce que l’app a enregistré cette semaine.', 'A semana conta a partir de segunda. É apenas um resumo de quanto o app registou esta semana.')
_tr7('insight.cue_dropouts', 'ここ数晩で心拍が {n} 回途切れ、そのたびにカウントがやり直しになっています。だから合図が少ないのです。時計はスマホの近くに（Bluetoothでつながっています）、スマホはWi‑Fiの電波が良い場所に。席を立つときはスマホも持っていってください。', '最近几个晚上心率中断了 {n} 次，每次中断计数都要重来 —— 所以提醒很少。让手表靠近手机（它们通过蓝牙连接），手机放在 Wi‑Fi 信号好的地方；起身时把手机一起带上。', 'За последние вечера пульс пропадал {n} раз, и каждый раз счёт начинается заново — поэтому подсказок мало. Держи часы рядом с телефоном (они связаны по Bluetooth), а телефон — там, где хороший Wi‑Fi; когда встаёшь, бери телефон с собой.', 'En las últimas noches tu pulso se cortó {n} veces, y cada corte reinicia la cuenta: por eso hay pocos avisos. Ten el reloj cerca del móvil (se conectan por Bluetooth) y el móvil con buena Wi‑Fi; cuando te levantes, llévate el móvil.', 'In den letzten Abenden fiel dein Puls {n}× aus, und jeder Ausfall startet die Zählung neu — daher die wenigen Hinweise. Halte die Uhr nah am Handy (sie sind über Bluetooth verbunden) und das Handy dort, wo das WLAN gut ist; wenn du aufstehst, nimm das Handy mit.', 'Ces derniers soirs, ton pouls a été perdu {n} fois, et chaque coupure relance le compte — d’où le peu de rappels. Garde la montre près du téléphone (ils sont reliés en Bluetooth) et le téléphone là où le Wi‑Fi est bon ; quand tu te lèves, prends le téléphone avec toi.', 'Nas últimas noites o teu pulso falhou {n}×, e cada falha reinicia a contagem — por isso há poucos avisos. Mantém o relógio perto do telemóvel (ligam‑se por Bluetooth) e o telemóvel com bom Wi‑Fi; quando te levantares, leva o telemóvel contigo.')
_tr7('insight.cue_never_above', '直近 {n} 晩、負荷は一度もしきい値を超えませんでした。だからアプリは声をかける理由がありませんでした。物足りなければ、時計の設定で心拍の上限を下げてみてください。', '最近 {n} 个晚上，负荷一次也没有越过阈值，所以应用没有理由出声。如果你觉得太少，可以在手表设置里调低心率上限。', 'За последние {n} вечера нагрузка ни разу не перешла порог, так что приложению нечего было сказать. Если этого мало, попробуй снизить потолок пульса в настройках часов.', 'En las últimas {n} noches la carga no superó el umbral ni una vez, así que la app no tenía motivo para hablar. Si te parece poco, baja el techo de pulso en los ajustes del reloj.', 'In den letzten {n} Abenden hat die Belastung die Schwelle nie überschritten, also hatte die App keinen Grund zu sprechen. Wenn dir das zu wenig ist, senke die Pulsobergrenze in den Uhr-Einstellungen.', 'Ces {n} derniers soirs, la charge n’a jamais dépassé le seuil : l’app n’avait aucune raison de parler. Si cela te semble peu, baisse le plafond de pouls dans les réglages de la montre.', 'Nas últimas {n} noites a carga nunca passou o limiar, por isso a app não teve motivo para falar. Se achas pouco, baixa o limite de pulso nas definições do relógio.')
_tr7('insight.cue_almost', '負荷は上がりましたが、連続で最長 {sec} 秒 — {need} 秒に届きませんでした。惜しいところです。「どれくらい声をかけるか」を一段上げてみてください。', '负荷确实升高了，但最长连续 {sec} 秒 —— 距离 {need} 秒还差一点。很接近了：可以把“多久提醒一次”调高一档。', 'Нагрузка поднималась, но дольше всего {sec} с подряд — не хватило до {need} с. Было близко: попробуй поднять «как часто я отзываюсь» на ступень выше.', 'La carga sí subió, pero lo más largo fueron {sec} s seguidos: faltó para {need} s. Estuvo cerca: prueba a subir un paso «cada cuánto hablo».', 'Die Belastung stieg, aber am längsten {sec} s am Stück — bis {need} s fehlte wenig. Es war knapp: stell „wie oft ich mich melde“ eine Stufe höher.', 'La charge est montée, mais au plus long {sec} s d’affilée — il manquait peu pour {need} s. C’était juste : monte « à quelle fréquence je parle » d’un cran.', 'A carga subiu, mas no máximo {sec} s seguidos — faltou para {need} s. Esteve perto: tenta subir um nível em «com que frequência falo».')
_tr7('insight.cue_far', '負荷はしきい値を超えましたが一瞬だけで、連続は最長 {sec} 秒（必要は {need} 秒）。あなたの体はアプリが待つより速く上下しています。待ち時間を縮めるより、心拍の上限を下げるほうが効きます。', '负荷确实越过了阈值，但只是一瞬 —— 最长连续 {sec} 秒，需要 {need} 秒。你的身体起伏比应用等待的更快。与其缩短等待，不如调低心率上限。', 'Нагрузка порог переходила, но лишь ненадолго — дольше всего {sec} с из нужных {need} с. Твоё тело поднимается и опускается быстрее, чем приложение ждёт. Стоит снизить потолок пульса, а не только сокращать ожидание.', 'La carga sí cruzó el umbral, pero solo un momento: lo más largo fueron {sec} s de los {need} s necesarios. Tu cuerpo sube y baja más rápido de lo que la app espera. Vale más bajar el techo de pulso que acortar la espera.', 'Die Belastung überschritt die Schwelle, aber nur kurz — am längsten {sec} s von nötigen {need} s. Dein Körper steigt und fällt schneller, als die App wartet. Es lohnt eher, die Pulsobergrenze zu senken, als nur die Wartezeit zu kürzen.', 'La charge a franchi le seuil, mais brièvement — au plus long {sec} s sur les {need} s requises. Ton corps monte et descend plus vite que l’app n’attend. Mieux vaut baisser le plafond de pouls que seulement raccourcir l’attente.', 'A carga passou o limiar, mas só por instantes — no máximo {sec} s dos {need} s necessários. O teu corpo sobe e desce mais depressa do que a app espera. Compensa baixar o limite de pulso, não só encurtar a espera.')
_tr7('insight.need_more', 'これまで {n}/{need} セッション — 3回そろうと、アプリはそれらを横断して傾向を探しはじめる。', '目前 {n}/{need} 次记录 — 满三次后，应用会开始跨记录寻找规律。', 'Пока {n} из {need} сессий — после трёх приложение начнёт искать закономерности между ними.', 'Por ahora {n} de {need} sesiones: a partir de tres, la app empieza a buscar patrones entre ellas.', 'Bisher {n} von {need} Sitzungen — ab drei sucht die App nach Mustern über sie hinweg.', 'Pour l’instant {n} séances sur {need} — à partir de trois, l’app commence à chercher des tendances.', 'Até agora {n} de {need} sessões — a partir de três, o app começa a procurar padrões entre elas.')
_tr7('insight.steady', '直近 {n} セッションで目立つものはない — 心拍も回復もしきい値超えの時間も安定している。', '最近 {n} 次记录没有异常 — 心率、恢复和超阈时间都很稳定。', 'За последние {n} сессий ничего не выделяется — пульс, восстановление и время выше порога стабильны.', 'En las últimas {n} sesiones no destaca nada: pulso, recuperación y tiempo sobre el límite son estables.', 'Über die letzten {n} Sitzungen fällt nichts auf — Puls, Erholung und Zeit über der Grenze sind stabil.', 'Rien ne ressort sur les {n} dernières séances — pouls, récupération et temps au-dessus du seuil sont stables.', 'Nas últimas {n} sessões nada se destaca — pulso, recuperação e tempo acima do limite estão estáveis.')
_tr7('insight.resting_up', '安静時心拍が先週より {delta} BPM 上がった — 睡眠不足、カフェイン、風邪かもしれない。必ずしもゲームのせいではない。', '静息心率比上周高了 {delta} BPM — 也许是睡得少、咖啡因或感冒？不一定是游戏造成的。', 'Пульс покоя вырос на {delta} уд/мин по сравнению с прошлой неделей — может, меньше сна, кофеин или простуда? Не обязательно из-за игры.', 'Tu pulso en reposo subió {delta} ppm frente a la semana anterior: ¿menos sueño, cafeína o un resfriado? No tiene por qué venir de jugar.', 'Dein Ruhepuls ist gegenüber der Vorwoche um {delta} S/min gestiegen — vielleicht weniger Schlaf, Koffein oder eine Erkältung? Nicht zwangsläufig vom Spielen.', 'Ton pouls au repos a monté de {delta} bpm par rapport à la semaine d’avant — moins de sommeil, caféine ou un rhume ? Pas forcément à cause du jeu.', 'O teu pulso em repouso subiu {delta} bpm face à semana anterior — talvez menos sono, cafeína ou uma constipação? Não vem necessariamente de jogares.')
_tr7('insight.resting_down', '安静時心拍が前の週より {delta} BPM 下がった — 体はよく休めているように見える。', '静息心率比上一周低了 {delta} BPM — 身体看起来休息得更好。', 'Пульс покоя упал на {delta} уд/мин по сравнению с прошлой неделей — тело выглядит более отдохнувшим.', 'Tu pulso en reposo bajó {delta} ppm frente a la semana anterior: tu cuerpo parece más descansado.', 'Dein Ruhepuls ist gegenüber der Vorwoche um {delta} S/min gesunken — dein Körper wirkt erholter.', 'Ton pouls au repos a baissé de {delta} bpm par rapport à la semaine d’avant — ton corps semble plus reposé.', 'O teu pulso em repouso desceu {delta} bpm face à semana anterior — o corpo parece mais descansado.')
_tr7('insight.hrr_up', '心拍回復が {delta} BPM 良くなった — 以前より速く落ち着いている。', '心率恢复提升了 {delta} BPM — 你比以前平静得更快。', 'Восстановление пульса улучшилось на {delta} уд/мин — ты успокаиваешься быстрее, чем раньше.', 'La recuperación del pulso mejoró {delta} ppm: te calmas más rápido que antes.', 'Die Herzfrequenz-Erholung hat sich um {delta} S/min verbessert — du kommst schneller runter als früher.', 'La récupération cardiaque s’est améliorée de {delta} bpm — tu redescends plus vite qu’avant.', 'A recuperação do pulso melhorou {delta} bpm — acalmas mais depressa do que antes.')
_tr7('insight.hrr_down', '心拍回復が以前より {delta} BPM 遅い — 緊張したあと下がるまでに時間がかかっている。クラッチの直後に呼吸を試してみて。', '心率恢复比以前慢了 {delta} BPM — 紧张之后要更久才降下来。试试在关键局之后马上做呼吸。', 'Восстановление пульса на {delta} уд/мин медленнее, чем раньше — после напряжённого момента он дольше не опускается. Попробуй подышать сразу после клатча.', 'La recuperación del pulso es {delta} ppm más lenta que antes: tarda más en bajar tras un momento tenso. Prueba a respirar justo después de un clutch.', 'Die Herzfrequenz-Erholung ist {delta} S/min langsamer als früher — nach einem angespannten Moment dauert es länger, bis der Puls fällt. Probier direkt nach einer Clutch zu atmen.', 'La récupération cardiaque est {delta} bpm plus lente qu’avant — il faut plus de temps pour redescendre après un moment tendu. Essaie de respirer juste après un clutch.', 'A recuperação do pulso está {delta} bpm mais lenta do que antes — demora mais a descer depois de um momento tenso. Experimenta respirar logo a seguir a um clutch.')
_tr7('insight.triggers_early', '呼吸の発動の {share} % が最初の1時間に起きている — セッションの入りが一番あおる。ウォームアップを落ち着かせるか、セッションを短くしてみて。', '{share} % 的呼吸触发发生在第一个小时 — 开局最容易让你上头。试试更平静的热身或更短的时段。', '{share} % запусков дыхания пришлись на первый час — начало сессии заводит сильнее всего; попробуй спокойнее разминку или более короткие сессии.', 'El {share} % de los lanzamientos de respiración ocurrió en la primera hora: el arranque es lo que más te acelera. Prueba un calentamiento más tranquilo o sesiones más cortas.', '{share} % der Atem-Auslösungen kamen in der ersten Stunde — der Einstieg puscht am meisten; probier ein ruhigeres Warm-up oder kürzere Sitzungen.', '{share} % des déclenchements de respiration sont arrivés dans la première heure — le début de séance t’excite le plus ; essaie un échauffement plus calme ou des séances plus courtes.', '{share} % dos disparos de respiração aconteceram na primeira hora — o arranque é o que mais te acelera; experimenta um aquecimento mais calmo ou sessões mais curtas.')
_tr7('insight.triggers_late', '呼吸の発動の {share} % が2時間を過ぎてから — 長いセッションが緊張を保たせている。休憩をはさんで短めにしてみて。', '{share} % 的呼吸触发发生在两小时之后 — 长时间会让你一直绷着。试试缩短时段并加入休息。', '{share} % запусков дыхания пришлись на время после двух часов — долгие сессии держат тебя в напряжении; попробуй более короткие с перерывом.', 'El {share} % de los lanzamientos de respiración llegó después de dos horas: las sesiones largas te mantienen tenso. Prueba sesiones más cortas con una pausa.', '{share} % der Atem-Auslösungen kamen nach zwei Stunden — lange Sitzungen halten dich angespannt; probier kürzere mit einer Pause.', '{share} % des déclenchements de respiration sont arrivés après deux heures — les longues séances te gardent tendu ; essaie plus court avec une pause.', '{share} % dos disparos de respiração vieram depois de duas horas — sessões longas mantêm-te tenso; experimenta mais curtas com uma pausa.')
_tr7('insight.over_up', '直近のセッションでしきい値超えの時間が増えている（平均 {minutes} 分） — ゲームが以前より長く緊張させている。まさに呼吸が効く場面。', '最近几次超阈时间变长了（平均 {minutes} 分钟）— 游戏让你绷得比以前久；这正是呼吸起作用的时候。', 'Время выше порога в последних сессиях выросло (в среднем {minutes} мин) — игра держит тебя в напряжении дольше, чем раньше; именно тогда помогает дыхание.', 'El tiempo por encima del límite ha crecido en las últimas sesiones (media {minutes} min): el juego te mantiene tenso más que antes, justo cuando la respiración ayuda.', 'Die Zeit über der Grenze ist in den letzten Sitzungen gewachsen (Schnitt {minutes} Min) — das Spiel hält dich länger angespannt als früher; genau dann hilft Atmen.', 'Le temps au-dessus du seuil a augmenté sur les dernières séances (moyenne {minutes} min) — le jeu te garde tendu plus longtemps qu’avant ; c’est là que respirer aide.', 'O tempo acima do limite cresceu nas últimas sessões (média {minutes} min) — o jogo mantém-te tenso mais tempo do que antes; é aí que respirar ajuda.')
_tr7('log.audio_reset', 'サウンドを推奨値に戻した', '声音已恢复为推荐值', 'Звук возвращён к рекомендуемым значениям', 'Sonido restaurado a los valores recomendados', 'Ton auf empfohlene Werte zurückgesetzt', 'Son remis aux valeurs recommandées', 'Som reposto nos valores recomendados')
_tr7('log.sessions_exported', 'エクスポート：{n} セッションを表に', '导出：{n} 次记录到表格', 'Экспорт: {n} сессий в таблицу', 'Exportación: {n} sesiones a una hoja de cálculo', 'Export: {n} Sitzungen in eine Tabelle', 'Export : {n} séances vers un tableur', 'Exportação: {n} sessões para uma folha de cálculo')
_tr7('log.slots_removed_bulk', '{n} 個のトリガーを削除した。', '已删除 {n} 个触发器。', 'Удалено триггеров: {n}.', 'Se eliminaron {n} disparadores.', '{n} Trigger entfernt.', '{n} déclencheurs supprimés.', 'Removidos {n} gatilhos.')
_tr7('log.hotkey_on', 'ショートカット {combo} が有効 — 30分間静かにします', '快捷键 {combo} 已就绪 — 会让我安静半小时', 'Сочетание {combo} готово — заглушит меня на полчаса', 'El atajo {combo} está listo: me silenciará media hora', 'Tastenkürzel {combo} ist bereit — es macht mich eine halbe Stunde still', 'Le raccourci {combo} est prêt — il me fera taire une demi-heure', 'O atalho {combo} está pronto — silencia-me por meia hora')
_tr7('log.hotkey_failed', '{combo} は別のアプリが使用中 — ドックのボタンは使えます', '{combo} 已被其他应用占用 — 仍可用停靠栏按钮', '{combo} занято другим приложением — кнопка в доке работает', 'Otra app usa {combo}: el botón del dock sigue funcionando', 'Eine andere App belegt {combo} — der Dock-Knopf funktioniert weiter', 'Une autre app occupe {combo} — le bouton du dock fonctionne toujours', 'Outra app usa {combo} — o botão do dock continua a funcionar')
_tr7('log.snooze_started', 'アプリを {minutes} 分ミュートした', '应用已静音 {minutes} 分钟', 'Приложение приостановлено на {minutes} минут', 'App en pausa durante {minutes} minutos', 'App für {minutes} Minuten pausiert', 'App mise en pause pendant {minutes} minutes', 'App em pausa durante {minutes} minutos')
_tr7('log.snooze_ended', 'ミュートが終わった', '静音结束', 'Пауза закончилась', 'La pausa terminó', 'Pause beendet', 'Pause terminée', 'A pausa terminou')
_tr7('log.snooze_cancelled', 'ミュートを解除した', '已取消静音', 'Пауза отменена', 'Pausa cancelada', 'Pause abgebrochen', 'Pause annulée', 'Pausa cancelada')
_tr7('log.hr_session_saved', 'セッションを保存 — 平均 {avg} BPM、最高 {max} BPM、負荷ピーク {peak}。', '记录已保存 — 平均 {avg} BPM，最高 {max} BPM，负荷峰值 {peak}。', 'Сессия сохранена — средний {avg} уд/мин, пик {max} уд/мин, пик нагрузки {peak}.', 'Sesión guardada: media {avg} ppm, pico {max} ppm, pico de carga {peak}.', 'Sitzung gespeichert — Schnitt {avg} S/min, Spitze {max} S/min, Last-Spitze {peak}.', 'Séance enregistrée — moyenne {avg} bpm, pic {max} bpm, pic de charge {peak}.', 'Sessão guardada — média {avg} bpm, pico {max} bpm, pico de carga {peak}.')
_tr7('log.monitor_target', 'ビジュアルと HUD は今後こちらに描画：{target}。', '视觉效果和 HUD 现在绘制在：{target}。', 'Визуалы и HUD теперь рисуются на: {target}.', 'Los visuales y el HUD se dibujarán ahora en: {target}.', 'Visuals und HUD werden jetzt gezeichnet auf: {target}.', 'Les visuels et le HUD se dessineront désormais sur : {target}.', 'Os visuais e o HUD passam a ser desenhados em: {target}.')
_tr7('log.exclusive_fullscreen', 'ゲームが排他的フルスクリーン — Windows はその上にオーバーレイを一切描かない。ゲームを「ボーダーレス」に切り替えないとビジュアルは見えない。', '游戏处于独占全屏 — Windows 不会在其上绘制任何覆盖层。请把游戏切换为“无边框”，否则看不到视觉效果。', 'Игра в эксклюзивном полноэкранном режиме — Windows не станет рисовать поверх неё никакой оверлей. Переключи игру в «Без рамки», иначе визуалов не увидишь.', 'El juego está en pantalla completa exclusiva: Windows no dibujará ningún overlay encima. Cambia el juego a «Sin bordes» o no verás los visuales.', 'Das Spiel läuft im exklusiven Vollbild — Windows zeichnet darüber kein Overlay. Stell das Spiel auf „Randlos“, sonst siehst du die Visuals nicht.', 'Le jeu est en plein écran exclusif — Windows ne dessinera aucun overlay par-dessus. Passe le jeu en « Sans bordure », sinon tu ne verras pas les visuels.', 'O jogo está em ecrã inteiro exclusivo — o Windows não desenha nenhum overlay por cima. Muda o jogo para «Sem margens» ou não verás os visuais.')
_tr7('guide.block.physiology', '体で起きていること', '身体里发生了什么', 'Что происходит в теле', 'Qué pasa en tu cuerpo', 'Was im Körper passiert', 'Ce qui se passe dans le corps', 'O que acontece no corpo')
_tr7('guide.block.science', '科学が言っていること', '科学怎么说', 'Что говорит наука', 'Qué dice la ciencia', 'Was die Wissenschaft sagt', 'Ce que dit la science', 'O que diz a ciência')
_tr7('guide.block.instruction', 'あなたがすること', '你要做什么', 'Что делаешь ты', 'Qué haces tú', 'Was du tust', 'Ce que tu fais', 'O que fazes')
_tr7('guide.philosophy.source4', 'PMC (2020) — 競技 e スポーツのセッション後の生理・認知機能（疲労）', 'PMC（2020）— 竞技电竞一场之后的生理与认知功能（疲劳）', 'PMC (2020) — физиологические и когнитивные функции после сессии соревновательного киберспорта (усталость)', 'PMC (2020) — funciones fisiológicas y cognitivas tras una sesión de esports competitivos (fatiga)', 'PMC (2020) — physiologische und kognitive Funktionen nach einer Session kompetitiver E-Sports (Ermüdung)', 'PMC (2020) — fonctions physiologiques et cognitives après une session d’esport compétitif (fatigue)', 'PMC (2020) — funções fisiológicas e cognitivas após uma sessão de esports competitivos (fadiga)')
_tr7('guide.philosophy.source6', 'Cleveland Clinic — 心拍回復：その意味と一般的な値', 'Cleveland Clinic — 心率恢复：含义与常见数值', 'Cleveland Clinic — восстановление пульса: что это значит и типичные значения', 'Cleveland Clinic — recuperación del pulso: qué significa y valores típicos', 'Cleveland Clinic — Herzfrequenz-Erholung: was sie bedeutet und typische Werte', 'Cleveland Clinic — récupération cardiaque : ce que cela signifie et valeurs typiques', 'Cleveland Clinic — recuperação do pulso: o que significa e valores típicos')
_tr7('guide.philosophy.source7', 'WHOOP — 心拍回復：回復が速いほど体力を映す理由', 'WHOOP — 心率恢复：为什么恢复更快反映体能', 'WHOOP — восстановление пульса: почему более быстрое восстановление отражает форму', 'WHOOP — recuperación del pulso: por qué una recuperación más rápida refleja la forma física', 'WHOOP — Herzfrequenz-Erholung: warum schnellere Erholung die Fitness widerspiegelt', 'WHOOP — récupération cardiaque : pourquoi une récupération plus rapide reflète la forme', 'WHOOP — recuperação do pulso: porque uma recuperação mais rápida reflete a forma física')
_tr7('guide.philosophy.source8', 'WHOOP — ストレス、安静時心拍と HRV：ストレスが心拍をどう変えるか（文脈情報。アプリは HRV を測らない）', 'WHOOP — 压力、静息心率与 HRV：压力如何改变心率（背景资料；本应用不测量 HRV）', 'WHOOP — стресс, пульс покоя и HRV: как стресс меняет пульс (контекст; приложение не измеряет HRV)', 'WHOOP — estrés, pulso en reposo y HRV: cómo el estrés cambia el pulso (contexto; la app no mide HRV)', 'WHOOP — Stress, Ruhepuls und HRV: wie Stress den Puls verändert (Kontext; die App misst kein HRV)', 'WHOOP — stress, pouls au repos et VFC : comment le stress change le pouls (contexte ; l’app ne mesure pas la VFC)', 'WHOOP — stress, pulso em repouso e HRV: como o stress muda o pulso (contexto; o app não mede HRV)')
_tr7('guide.philosophy.source9', 'bioRxiv (2026) — Heart Rate Persistence Index：心拍の高さと持続を一つの数字に', 'bioRxiv（2026）— Heart Rate Persistence Index：把心率的高度与持续时间合为一个数字', 'bioRxiv (2026) — Heart Rate Persistence Index: высота и длительность пульса в одном числе', 'bioRxiv (2026) — Heart Rate Persistence Index: altura y duración del pulso en un solo número', 'bioRxiv (2026) — Heart Rate Persistence Index: Höhe und Dauer des Pulses in einer Zahl', 'bioRxiv (2026) — Heart Rate Persistence Index : hauteur et durée du pouls en un seul chiffre', 'bioRxiv (2026) — Heart Rate Persistence Index: altura e duração do pulso num só número')
_tr7('guide.philosophy.source10', 'PubMed (2024) — “Heartbeats and high scores”：e スポーツは心血管系と自律神経のストレス反応を引き起こす', 'PubMed（2024）— “Heartbeats and high scores”：电竞会引发心血管与自主神经的应激反应', 'PubMed (2024) — «Heartbeats and high scores»: киберспорт вызывает сердечно-сосудистую и вегетативную стресс-реакцию', 'PubMed (2024) — «Heartbeats and high scores»: los esports desencadenan una respuesta de estrés cardiovascular y autonómica', 'PubMed (2024) — „Heartbeats and high scores“: E-Sport löst eine kardiovaskuläre und autonome Stressreaktion aus', 'PubMed (2024) — « Heartbeats and high scores » : l’esport déclenche une réponse de stress cardiovasculaire et autonome', 'PubMed (2024) — «Heartbeats and high scores»: os esports desencadeiam uma resposta de stress cardiovascular e autonómica')
_tr7('hud.section_title', 'ゲーム中の心拍パネル', '游戏中的心率面板', 'Панель пульса в игре', 'Panel de pulso en el juego', 'Puls-Panel im Spiel', 'Panneau de pouls en jeu', 'Painel de pulso no jogo')
_tr7('hud.enable', 'ゲーム中にパネルを表示', '在游戏中显示面板', 'Показывать панель в игре', 'Mostrar el panel en el juego', 'Panel im Spiel zeigen', 'Afficher le panneau en jeu', 'Mostrar o painel no jogo')
_tr7('hud.hint', '隅に出る小さなパネル：心拍、直近3分、負荷、セッションの進み。クリックはゲームに通り、Alt+Tab には出ない。', '角落里的小面板：心率、最近 3 分钟、负荷和本次进度。点击会穿透到游戏，也不会出现在 Alt+Tab 中。', 'Маленькая панель в углу: пульс, последние 3 минуты, нагрузка и ход сессии. Клики проходят в игру, в Alt+Tab она не появляется.', 'Un panel pequeño en la esquina: tu pulso, los últimos 3 minutos, la carga y el avance de la sesión. Los clics pasan al juego y nunca aparece en Alt+Tab.', 'Ein kleines Eckpanel: dein Puls, die letzten 3 Minuten, Last und Sitzungsverlauf. Klicks gehen ans Spiel durch, und es taucht nie im Alt+Tab auf.', 'Un petit panneau dans un coin : ton pouls, les 3 dernières minutes, la charge et l’avancée de la séance. Les clics passent au jeu et il n’apparaît jamais dans l’Alt+Tab.', 'Um painel pequeno no canto: o teu pulso, os últimos 3 minutos, a carga e o avanço da sessão. Os cliques passam para o jogo e nunca aparece no Alt+Tab.')
_tr7('hud.opacity', '不透明度', '不透明度', 'Непрозрачность', 'Opacidad', 'Deckkraft', 'Opacité', 'Opacidade')
_tr7('hud.test', 'HUD を 4 秒表示', '显示 HUD 4 秒', 'Показать HUD на 4 с', 'Mostrar el HUD 4 s', 'HUD 4 s zeigen', 'Afficher le HUD 4 s', 'Mostrar o HUD 4 s')
_tr7('hud.load', '負荷', '负荷', 'НАГРУЗКА', 'CARGA', 'LAST', 'CHARGE', 'CARGA')
_tr7('hud.waiting', 'データ待ち', '等待数据', 'ЖДУ ДАННЫЕ', 'ESPERANDO DATOS', 'WARTE AUF DATEN', 'EN ATTENTE DE DONNÉES', 'À ESPERA DE DADOS')
_tr7('hud.zone.calm', '平静', '平静', 'Покой', 'Calma', 'Ruhig', 'Calme', 'Calmo')
_tr7('hud.zone.raised', 'やや上昇', '略高', 'Повышенная', 'Elevada', 'Erhöht', 'Élevée', 'Elevada')
_tr7('hud.zone.high', '高い', '偏高', 'Высокая', 'Alta', 'Hoch', 'Haute', 'Alta')
_tr7('hud.zone.critical', '危険域', '临界', 'Критическая', 'Crítica', 'Kritisch', 'Critique', 'Crítica')
_tr7('hud.session.triggers', 'リマインダー {n}', '提醒 {n}', 'НАПОМИНАНИЙ {n}', 'RECORDATORIOS {n}', 'ERINNERUNGEN {n}', 'RAPPELS {n}', 'LEMBRETES {n}')
_tr7('hud.session.over', 'しきい値超え {time}', '超阈 {time}', 'ВЫШЕ ПОРОГА {time}', 'SOBRE EL LÍMITE {time}', 'ÜBER DER GRENZE {time}', 'AU-DESSUS DU SEUIL {time}', 'ACIMA DO LIMITE {time}')
_tr7('hud.trigger_row.title', 'ゲーム中の機能アイコン', '游戏中的功能图标', 'Значки функций в игре', 'Iconos de funciones en el juego', 'Funktionssymbole im Spiel', 'Icônes de fonctions en jeu', 'Ícones de funções no jogo')
_tr7('hud.trigger_row.toggle', 'ゲーム中にアイコンを表示', '在游戏中显示图标', 'Показывать значки в игре', 'Mostrar iconos en el juego', 'Symbole im Spiel zeigen', 'Afficher les icônes en jeu', 'Mostrar ícones no jogo')
_tr7('hud.trigger_row.sub', '心拍と4つの基本機能だけの小さなパネルをゲーム中に — 画面上のビジュアルを減らしたい人向け。', '游戏中一个只有心率和 4 个基本功能的小面板 — 适合不想要太多屏幕视觉的人。', 'Маленькая панель с пульсом и четырьмя базовыми функциями прямо в игре — для тех, кто хочет меньше визуалов на экране.', 'Un panel pequeño con el pulso y las 4 funciones básicas dentro del juego, para quien quiere menos visuales en pantalla.', 'Ein kleines Panel mit Puls und den 4 Grundfunktionen direkt im Spiel — für alle, die weniger Visuals auf dem Bildschirm wollen.', 'Un petit panneau avec le pouls et les 4 fonctions de base directement en jeu — pour qui veut moins de visuels à l’écran.', 'Um painel pequeno com o pulso e as 4 funções básicas dentro do jogo — para quem quer menos visuais no ecrã.')
_tr7('hud.trigger_row.color', 'アイコンの色', '图标颜色', 'Цвет значков', 'Color de los iconos', 'Symbolfarbe', 'Couleur des icônes', 'Cor dos ícones')
_tr7('hud.trigger_row.color_theme', 'テーマの色', '主题色', 'Цвет темы', 'Color del tema', 'Themenfarbe', 'Couleur du thème', 'Cor do tema')
_tr7('hud.snooze.5min', '5 分', '5 分钟', '5 минут', '5 minutos', '5 Minuten', '5 minutes', '5 minutos')
_tr7('hud.snooze.20min', '20 分', '20 分钟', '20 минут', '20 minutos', '20 Minuten', '20 minutes', '20 minutos')
_tr7('hud.snooze.40min', '40 分', '40 分钟', '40 минут', '40 minutos', '40 Minuten', '40 minutes', '40 minutos')
_tr7('hud.snooze.60min', '60 分', '60 分钟', '60 минут', '60 minutos', '60 Minuten', '60 minutes', '60 minutos')
_tr7('hud.snooze.cancel', 'ミュートを解除', '取消静音', 'Отменить паузу', 'Cancelar la pausa', 'Pause aufheben', 'Annuler la pause', 'Cancelar a pausa')
_tr7('overlay.dialog_title', 'ゲーム中のビジュアル', '游戏中的视觉效果', 'Визуалы в игре', 'Visuales en el juego', 'Visuals im Spiel', 'Visuels en jeu', 'Visuais no jogo')
_tr7('overlay.caption.grounding', '重心を落とせ', '沉下重心', 'ОПУСТИ ЦЕНТР ТЯЖЕСТИ', 'BAJA EL PESO', 'GEWICHT SENKEN', 'RELÂCHE TON POIDS', 'BAIXA O PESO')
_tr7('overlay.caption.jaw', '顎をゆるめろ', '松开下巴', 'РАССЛАБЬ ЧЕЛЮСТЬ', 'AFLOJA LA MANDÍBULA', 'KIEFER LOCKERN', 'DESSERRE LA MÂCHOIRE', 'SOLTA O MAXILAR')
_tr7('overlay.caption.release', '握りをゆるめろ', '松开握力', 'ОСЛАБЬ ХВАТ', 'AFLOJA LA MANO', 'GRIFF LOCKERN', 'RELÂCHE TA PRISE', 'SOLTA A MÃO')
_tr7('overlay.caption.inhale', '吸って', '吸气', 'ВДОХ', 'INSPIRA', 'EINATMEN', 'INSPIRE', 'INSPIRA')
_tr7('overlay.caption.exhale', '吐いて', '呼气', 'ВЫДОХ', 'ESPIRA', 'AUSATMEN', 'EXPIRE', 'EXPIRA')
_tr7('overlay.monitor.label', 'どの画面に描くか', '在哪块屏幕上绘制', 'На каком экране рисовать', 'En qué pantalla dibujar', 'Auf welchem Bildschirm zeichnen', 'Sur quel écran dessiner', 'Em que ecrã desenhar')
_tr7('overlay.monitor.pick', '画面', '屏幕', 'Экран', 'Pantalla', 'Bildschirm', 'Écran', 'Ecrã')
_tr7('overlay.monitor.auto', '自動（ゲームが動いている画面）', '自动（游戏所在的屏幕）', 'Автоматически (где идёт игра)', 'Automático (donde corre el juego)', 'Automatisch (wo das Spiel läuft)', 'Automatique (où tourne le jeu)', 'Automático (onde corre o jogo)')
_tr7('overlay.monitor.cursor', 'カーソルのある画面', '光标所在的屏幕', 'Где курсор', 'Donde está el cursor', 'Wo der Cursor ist', 'Où est le curseur', 'Onde está o cursor')
_tr7('overlay.monitor.primary', 'メインモニター', '主显示器', 'Основной монитор', 'Monitor principal', 'Hauptmonitor', 'Moniteur principal', 'Monitor principal')
_tr7('overlay.monitor.hint', '「自動」ならアプリはアクティブなウィンドウのある画面 — つまり今プレイしている画面 — に描く。', '选“自动”时，应用会画在当前活动窗口所在的屏幕上 — 也就是你正在玩的那块。', 'При «Автоматически» приложение рисует на том экране, где активное окно, — то есть на том, где ты играешь.', 'Con «Automático» la app dibuja en la pantalla que tiene la ventana activa, es decir, en la que estás jugando.', 'Bei „Automatisch“ zeichnet die App auf dem Bildschirm mit dem aktiven Fenster — also dem, auf dem du spielst.', 'Avec « Automatique », l’app dessine sur l’écran qui a la fenêtre active — celui sur lequel tu joues.', 'Com «Automático» o app desenha no ecrã que tem a janela ativa — aquele em que estás a jogar.')
_tr7('overlay.fine_tune', 'サイズと位置を微調整…', '微调大小和位置…', 'Точная настройка размера и положения…', 'Ajustar tamaño y posición…', 'Größe und Position feinjustieren…', 'Ajuster finement taille et position…', 'Afinar tamanho e posição…')
_tr7('overlay.test_done', '完了', '完成', 'Готово', 'Listo', 'Fertig', 'Terminé', 'Pronto')
_tr7('overlay.drag_hint', '「テスト」を押すとアイコンが画面に出る — マウスでつかんで好きな場所へドラッグ。もう一度クリックすると位置が保存される。', '点击“测试”，图标会出现在屏幕上 — 用鼠标抓住拖到你想要的位置。再点一次即可保存位置。', 'Нажми «Тест» — значок появится на экране; хватай мышью и тащи куда хочешь. Ещё один клик сохранит положение.', 'Pulsa «Probar» y el icono aparece en pantalla: agárralo con el ratón y arrástralo donde quieras. Otro clic guarda la posición.', 'Klick auf „Test“ und das Symbol erscheint auf dem Bildschirm — pack es mit der Maus und zieh es, wohin du willst. Ein weiterer Klick speichert die Position.', 'Clique sur « Test » et l’icône apparaît à l’écran — attrape-la à la souris et place-la où tu veux. Un autre clic enregistre la position.', 'Clica em «Testar» e o ícone aparece no ecrã — agarra-o com o rato e arrasta para onde quiseres. Outro clique guarda a posição.')
_tr7('overlay.color_title', 'アイコンの色', '图标颜色', 'Цвет значка', 'Color del icono', 'Symbolfarbe', 'Couleur de l’icône', 'Cor do ícone')
_tr7('overlay.breath_seconds', '呼吸のサイクル（秒）', '呼吸周期（秒）', 'Цикл дыхания (в секундах)', 'Ciclo de respiración (en segundos)', 'Atemzyklus (in Sekunden)', 'Cycle de respiration (en secondes)', 'Ciclo de respiração (em segundos)')
_tr7('overlay.breath_inhale', '吸う長さ（秒）', '吸气时长（秒）', 'Длина вдоха (с)', 'Duración de la inspiración (s)', 'Länge des Einatmens (s)', 'Durée de l’inspiration (s)', 'Duração da inspiração (s)')
_tr7('overlay.breath_exhale', '吐く長さ（秒）', '呼气时长（秒）', 'Длина выдоха (с)', 'Duración de la espiración (s)', 'Länge des Ausatmens (s)', 'Durée de l’expiration (s)', 'Duração da expiração (s)')
_tr7('hr.pair_button', '時計のつなぎ方…', '如何连接手表…', 'Как подключить часы…', 'Cómo vincular tu reloj…', 'Uhr verbinden…', 'Comment connecter ta montre…', 'Como ligar o teu relógio…')
_tr7('hr.pair_title', '時計をつなぐ', '连接你的手表', 'Подключение часов', 'Vincular tu reloj', 'Uhr verbinden', 'Connecter ta montre', 'Ligar o teu relógio')
_tr7('hr.pair_intro', 'アプリは OBS のふりをする — 電話が「HeartRateOnStream for OBS」経由で心拍を送る。一度設定すれば、あとは勝手に動く。', '应用会伪装成 OBS — 手机通过 “HeartRateOnStream for OBS” 把心率发过来。设置一次，之后就自动运行。', 'Приложение притворяется OBS — телефон шлёт пульс через приложение «HeartRateOnStream for OBS». Настроишь один раз, дальше работает само.', 'La app se hace pasar por OBS: tu móvil envía el pulso a través de «HeartRateOnStream for OBS». Lo configuras una vez y ya funciona solo.', 'Die App gibt sich als OBS aus — dein Handy sendet den Puls über die App „HeartRateOnStream for OBS“. Einmal einrichten, dann läuft es von selbst.', 'L’app se fait passer pour OBS — ton téléphone envoie le pouls via l’app « HeartRateOnStream for OBS ». Tu configures une fois, ensuite ça tourne tout seul.', 'O app faz-se passar por OBS — o telemóvel envia o pulso através da app «HeartRateOnStream for OBS». Configuras uma vez e depois corre sozinho.')
_tr7('hr.pair_this_pc', 'この PC のアドレスとポート — 電話に入力する', '这台电脑的地址和端口 — 输入到手机里', 'АДРЕС И ПОРТ ЭТОГО ПК — введи их в телефоне', 'DIRECCIÓN Y PUERTO DE ESTE PC: escríbelos en el móvil', 'ADRESSE UND PORT DIESES PCS — im Handy eintragen', 'ADRESSE ET PORT DE CE PC — à saisir sur le téléphone', 'ENDEREÇO E PORTA DESTE PC — escreve-os no telemóvel')
_tr7('hr.pair_ip_unknown', 'IP を検出できなかった', '无法检测到 IP', 'Не удалось определить IP', 'No se pudo detectar la IP', 'IP konnte nicht erkannt werden', 'Impossible de détecter l’IP', 'Não foi possível detetar o IP')
_tr7('hr.pair_ip_help', 'コマンドプロンプトを開いて ipconfig と入力 — 「IPv4 アドレス」を探す（たいてい 192.168.x.x）。電話と PC は同じ Wi‑Fi にいる必要がある。', '打开命令提示符输入 ipconfig — 找到 “IPv4 地址”（通常是 192.168.x.x）。手机和电脑必须在同一个 Wi‑Fi 上。', 'Открой командную строку и набери ipconfig — найди «IPv4-адрес» (обычно 192.168.x.x). Телефон и ПК должны быть в одном Wi‑Fi.', 'Abre el símbolo del sistema y escribe ipconfig: busca «Dirección IPv4» (suele ser 192.168.x.x). El móvil y el PC deben estar en el mismo Wi‑Fi.', 'Öffne die Eingabeaufforderung und tippe ipconfig — such nach „IPv4-Adresse“ (meist 192.168.x.x). Handy und PC müssen im selben WLAN sein.', 'Ouvre l’invite de commandes et tape ipconfig — cherche « Adresse IPv4 » (souvent 192.168.x.x). Le téléphone et le PC doivent être sur le même Wi‑Fi.', 'Abre a Linha de Comandos e escreve ipconfig — procura «Endereço IPv4» (normalmente 192.168.x.x). Telemóvel e PC têm de estar no mesmo Wi‑Fi.')
_tr7('hr.pair_other_ips', 'この PC の他のアドレス（最初のが効かない場合）：{ips}', '这台电脑的其他地址（如果第一个不行）：{ips}', 'Другие адреса этого ПК (если первый не работает): {ips}', 'Otras direcciones de este PC (si la primera no funciona): {ips}', 'Weitere Adressen dieses PCs (falls die erste nicht geht): {ips}', 'Autres adresses de ce PC (si la première ne marche pas) : {ips}', 'Outros endereços deste PC (se o primeiro não funcionar): {ips}')
_tr7('hr.pair_ip_note', '設定では 0.0.0.0 のままにする — この番号は電話に入れるためだけのもの。', '设置里保持 0.0.0.0 — 这个号码只用来填进手机。', 'В настройках оставь 0.0.0.0 — это число идёт только в телефон.', 'Deja 0.0.0.0 en los ajustes: este número solo se escribe en el móvil.', 'Lass in den Einstellungen 0.0.0.0 — diese Zahl kommt nur ins Handy.', 'Laisse 0.0.0.0 dans les réglages — ce numéro ne sert qu’au téléphone.', 'Deixa 0.0.0.0 nas definições — este número só vai para o telemóvel.')
_tr7('hr.step1_title', '同じ Wi‑Fi', '同一个 Wi‑Fi', 'Один Wi‑Fi', 'El mismo Wi‑Fi', 'Dasselbe WLAN', 'Le même Wi‑Fi', 'O mesmo Wi‑Fi')
_tr7('hr.step1_body', '時計とつながった電話と、この PC が同じ Wi‑Fi にいること（モバイル通信ではない）。', '连着手表的手机和这台电脑要在同一个 Wi‑Fi 上（不是移动数据）。', 'Телефон с часами и этот ПК — в одном Wi‑Fi (не в мобильном интернете).', 'El móvil con el reloj y este PC en el mismo Wi‑Fi (no datos móviles).', 'Handy mit der Uhr und dieser PC im selben WLAN (nicht mobile Daten).', 'Le téléphone avec la montre et ce PC sur le même Wi‑Fi (pas en données mobiles).', 'O telemóvel com o relógio e este PC no mesmo Wi‑Fi (não dados móveis).')
_tr7('hr.step2_title', '電話にアプリを入れる', '安装手机应用', 'Установи приложение на телефон', 'Instala la app del móvil', 'Handy-App installieren', 'Installe l’app du téléphone', 'Instala a app do telemóvel')
_tr7('hr.step2_body', 'Android / Wear OS：Google Play の「HeartRateOnStream for OBS」。iPhone / Apple Watch：App Store の「PulseOSC」— OSC を送り、このアプリもそれを理解する。下のコードを読み取って、時計とつないで。', 'Android / Wear OS：Google Play 的 “HeartRateOnStream for OBS”。iPhone / Apple Watch：App Store 的 “PulseOSC” — 它发送 OSC，本应用同样能理解。扫描下面的码，然后连上你的手表。', 'Android / Wear OS: «HeartRateOnStream for OBS» из Google Play. iPhone / Apple Watch: «PulseOSC» из App Store — она шлёт OSC, который это приложение тоже понимает. Отсканируй код ниже и подключи её к часам.', 'Android / Wear OS: «HeartRateOnStream for OBS» en Google Play. iPhone / Apple Watch: «PulseOSC» en la App Store: envía OSC, que esta app también entiende. Escanea un código de abajo y conéctala a tu reloj.', 'Android / Wear OS: „HeartRateOnStream for OBS“ aus Google Play. iPhone / Apple Watch: „PulseOSC“ aus dem App Store — sie sendet OSC, das diese App ebenfalls versteht. Scanne unten einen Code und verbinde sie mit deiner Uhr.', 'Android / Wear OS : « HeartRateOnStream for OBS » sur Google Play. iPhone / Apple Watch : « PulseOSC » sur l’App Store — elle envoie de l’OSC, que cette app comprend aussi. Scanne un code ci-dessous et connecte-la à ta montre.', 'Android / Wear OS: «HeartRateOnStream for OBS» no Google Play. iPhone / Apple Watch: «PulseOSC» na App Store — envia OSC, que este app também entende. Lê um código abaixo e liga-a ao teu relógio.')
_tr7('hr.step3_title', 'アドレスとポートを入れる', '输入地址和端口', 'Введи адрес и порт', 'Escribe la dirección y el puerto', 'Adresse und Port eintragen', 'Saisis l’adresse et le port', 'Introduz o endereço e a porta')
_tr7('hr.step3_body', '電話のアプリに、上の枠のアドレスとポートを入力する。パスワードは空のままでいい。', '在手机应用里填入上方框里的地址和端口。密码留空。', 'В приложении на телефоне введи адрес и порт из рамки выше. Пароль оставь пустым.', 'En la app del móvil introduce la dirección y el puerto del recuadro de arriba. Deja la contraseña vacía.', 'Trag in der Handy-App die Adresse und den Port aus dem Feld oben ein. Das Passwort bleibt leer.', 'Dans l’app du téléphone, saisis l’adresse et le port du cadre ci-dessus. Laisse le mot de passe vide.', 'Na app do telemóvel introduz o endereço e a porta da caixa acima. Deixa a palavra-passe vazia.')
_tr7('hr.step4_title', 'シーンとソースを選ぶ', '选择场景和来源', 'Выбери сцену и источник', 'Elige la escena y la fuente', 'Szene und Quelle wählen', 'Choisis la scène et la source', 'Escolhe a cena e a fonte')
_tr7('hr.step4_body', 'つながったら、シーン「Zanshin」とソース「Heart rate」を選ぶ。', '连接之后，选择场景 “Zanshin” 和来源 “Heart rate”。', 'После подключения выбери сцену «Zanshin» и источник «Heart rate».', 'Una vez conectado, elige la escena «Zanshin» y la fuente «Heart rate».', 'Sobald verbunden, wähle die Szene „Zanshin“ und die Quelle „Heart rate“.', 'Une fois connecté, choisis la scène « Zanshin » et la source « Heart rate ».', 'Depois de ligado, escolhe a cena «Zanshin» e a fonte «Heart rate».')
_tr7('hr.step5_title', 'ここでセンサーを入れる', '在这里打开传感器', 'Включи датчик здесь', 'Activa el sensor aquí', 'Sensor hier einschalten', 'Active le capteur ici', 'Liga o sensor aqui')
_tr7('hr.step5_body', 'ここに戻って「時計から心拍を受け取る」を入れる。数秒で見えるはず。', '回到这里，打开“接收手表的心率”。几秒内就能看到。', 'Вернись сюда и включи «Слушать пульс с часов». Увидишь его через пару секунд.', 'Vuelve aquí y activa «Escuchar el pulso del reloj». Lo verás en unos segundos.', 'Komm hierher zurück und schalte „Puls von der Uhr empfangen“ ein. Du siehst ihn in Sekunden.', 'Reviens ici et active « Écouter le pouls de la montre ». Tu le verras en quelques secondes.', 'Volta aqui e liga «Ouvir o pulso do relógio». Vais vê-lo em segundos.')
_tr7('hr.trouble_title', '時計はつながるのに心拍が来ない？', '手表连上了却没有心率？', 'Часы подключаются, а пульса нет?', '¿El reloj conecta pero no llega el pulso?', 'Uhr verbindet sich, aber kein Puls?', 'La montre se connecte mais pas de pouls ?', 'O relógio liga mas não chega pulso?')
_tr7('hr.trouble_body', '電話側でシーン「Zanshin」とソース「Heart rate」を確認し、時計が実際に測っているかも見て。別のプログラムがポートを取っているなら、ここと電話の両方で番号を変える。', '检查手机上的场景 “Zanshin” 和来源 “Heart rate”，并确认手表确实在测量。如果端口被别的程序占用，就在这里和手机上一起改。', 'Проверь на телефоне сцену «Zanshin» и источник «Heart rate», а также что часы действительно измеряют. Если порт занят другой программой, поменяй его здесь и в телефоне.', 'Comprueba en el móvil la escena «Zanshin» y la fuente «Heart rate», y que el reloj esté midiendo de verdad. Si otro programa ocupó el puerto, cámbialo aquí y en el móvil.', 'Prüfe am Handy die Szene „Zanshin“ und die Quelle „Heart rate“ und ob die Uhr wirklich misst. Wenn ein anderes Programm den Port belegt, ändere ihn hier und am Handy.', 'Vérifie sur le téléphone la scène « Zanshin » et la source « Heart rate », et que la montre mesure vraiment. Si un autre programme a pris le port, change-le ici et sur le téléphone.', 'Verifica no telemóvel a cena «Zanshin» e a fonte «Heart rate», e se o relógio está mesmo a medir. Se outro programa ocupou a porta, muda-a aqui e no telemóvel.')
_tr7('hr.qr_show', '電話で読み取る', '用手机扫描', 'Отсканировать телефоном', 'Escanear con el móvil', 'Mit dem Handy scannen', 'Scanner avec le téléphone', 'Ler com o telemóvel')
_tr7('hr.qr_hide', 'コードを隠す', '隐藏二维码', 'Скрыть коды', 'Ocultar los códigos', 'Codes ausblenden', 'Masquer les codes', 'Esconder os códigos')
_tr7('hr.qr_android', 'Android / Wear OS\n「HeartRateOnStream for OBS」（無料）。\nこの PC の IP とポートをその中で設定。', 'Android / Wear OS\n“HeartRateOnStream for OBS”（免费）。\n在里面填上这台电脑的 IP 和端口。', 'Android / Wear OS\n«HeartRateOnStream for OBS» (бесплатно).\nВнутри укажи IP и порт этого ПК.', 'Android / Wear OS\n«HeartRateOnStream for OBS» (gratis).\nDentro pon la IP y el puerto de este PC.', 'Android / Wear OS\n„HeartRateOnStream for OBS“ (kostenlos).\nDarin IP und Port dieses PCs eintragen.', 'Android / Wear OS\n« HeartRateOnStream for OBS » (gratuit).\nY saisir l’IP et le port de ce PC.', 'Android / Wear OS\n«HeartRateOnStream for OBS» (grátis).\nLá dentro define o IP e a porta deste PC.')
_tr7('hr.qr_ios', 'iPhone / Apple Watch\n「PulseOSC」（有料）。\nOSC を送る — この PC の IP とポートをその中で設定。', 'iPhone / Apple Watch\n“PulseOSC”（付费）。\n它发送 OSC — 在里面填上这台电脑的 IP 和端口。', 'iPhone / Apple Watch\n«PulseOSC» (платно).\nШлёт OSC — внутри укажи IP и порт этого ПК.', 'iPhone / Apple Watch\n«PulseOSC» (de pago).\nEnvía OSC: dentro pon la IP y el puerto de este PC.', 'iPhone / Apple Watch\n„PulseOSC“ (kostenpflichtig).\nSendet OSC — darin IP und Port dieses PCs eintragen.', 'iPhone / Apple Watch\n« PulseOSC » (payant).\nEnvoie de l’OSC — y saisir l’IP et le port de ce PC.', 'iPhone / Apple Watch\n«PulseOSC» (pago).\nEnvia OSC — lá dentro define o IP e a porta deste PC.')
_tr7('hr.qr_note', 'どちらも他社のアプリで、うちのものではない — こちらはただ受け取れるだけ。', '这两个都是别人的应用，不是我们的 — 我们只是能接收它们。', 'Оба приложения чужие, не наши — мы просто умеем их слушать.', 'Ambas apps son de otros, no nuestras: nosotros solo sabemos escucharlas.', 'Beide Apps gehören anderen, nicht uns — wir können ihnen nur zuhören.', 'Les deux apps appartiennent à d’autres, pas à nous — on sait juste les écouter.', 'Ambas as apps são de outros, não nossas — nós apenas sabemos ouvi-las.')
_tr7('settings.title', 'サウンドと音声', '声音与语音', 'Звук и голос', 'Sonido y voz', 'Ton und Stimme', 'Son et voix', 'Som e voz')
_tr7('settings.auto_profile', '起動中のゲームに合わせてプロファイルを自動で切り替える', '根据正在运行的游戏自动切换配置', 'Переключать профиль сам по запущенной игре', 'Cambiar el perfil solo según el juego en marcha', 'Profil je nach laufendem Spiel selbst wechseln', 'Changer le profil tout seul selon le jeu lancé', 'Trocar o perfil sozinho conforme o jogo em execução')
_tr7('settings.auto_profile_unavailable', 'ゲームによる自動切り替えは今は使えない（psutil ライブラリがない）', '目前无法按游戏自动切换（缺少 psutil 库）', 'Автопереключение по игре сейчас недоступно (нет библиотеки psutil)', 'El cambio automático por juego no está disponible ahora (falta la librería psutil)', 'Automatischer Wechsel nach Spiel ist gerade nicht verfügbar (Bibliothek psutil fehlt)', 'Le changement automatique par jeu n’est pas disponible (bibliothèque psutil manquante)', 'A troca automática por jogo não está disponível agora (falta a biblioteca psutil)')
_tr7('settings.overlay_button', '🎮 ゲーム中のビジュアル…', '🎮 游戏中的视觉效果…', '🎮 Визуалы в игре…', '🎮 Visuales en el juego…', '🎮 Visuals im Spiel…', '🎮 Visuels en jeu…', '🎮 Visuais no jogo…')
_tr7('settings.strict_global_lock', '一度にリマインダーは一つ', '同一时间只有一个提醒', 'Одно напоминание за раз', 'Un recordatorio a la vez', 'Eine Erinnerung auf einmal', 'Un rappel à la fois', 'Um lembrete de cada vez')
_tr7('settings.strict_global_lock_short', '一度にリマインダーは一つ', '同一时间只有一个提醒', 'Одно напоминание за раз', 'Un recordatorio a la vez', 'Eine Erinnerung auf einmal', 'Un rappel à la fois', 'Um lembrete de cada vez')
_tr7('settings.strict_global_lock_sub', '一つが鳴っているあいだ、他は黙る — でないと激しい撃ち合いで重なってしまう。', '一个在播放时其他保持安静 — 否则激烈交火时会叠在一起。', 'Пока играет одно, остальные молчат — иначе в плотной перестрелке они наложатся.', 'Mientras suena uno, los demás callan; de lo contrario se solapan en un tiroteo intenso.', 'Während eine läuft, schweigen die anderen — sonst überlagern sie sich im hitzigen Gefecht.', 'Pendant qu’un joue, les autres se taisent — sinon ils se chevauchent dans une fusillade dense.', 'Enquanto um toca, os outros calam-se — senão sobrepõem-se num tiroteio intenso.')
_tr7('settings.hr_section_title', '時計と心拍', '手表与心率', 'Часы и пульс', 'Reloj y pulso', 'Uhr und Puls', 'Montre et pouls', 'Relógio e pulso')
_tr7('settings.hr_ip_hint', '0.0.0.0 のままでいい（すべてで待ち受ける） — 迷ったら下の「時計のつなぎ方」を見て。', '保持 0.0.0.0（在所有网卡上监听）— 不确定就看下面的“如何连接手表”。', 'Оставь 0.0.0.0 (слушает везде) — не уверен? Смотри «Как подключить часы» ниже.', 'Deja 0.0.0.0 (escucha en todas partes); ¿no estás seguro? Mira «Cómo vincular tu reloj» abajo.', 'Lass 0.0.0.0 (lauscht überall) — unsicher? Siehe unten „Uhr verbinden“.', 'Laisse 0.0.0.0 (écoute partout) — pas sûr ? Vois « Comment connecter ta montre » ci-dessous.', 'Deixa 0.0.0.0 (ouve em todo o lado) — na dúvida, vê «Como ligar o teu relógio» abaixo.')
_tr7('settings.hr_port_hint', '分からなければ 4455 のまま — 時計のアプリにも同じ番号が必要。', '不清楚就保持 4455 — 手表应用里也要填同一个号码。', 'Оставь 4455, если не знаешь лучше — в приложении часов нужен тот же номер.', 'Deja 4455 salvo que sepas otra cosa: la app del reloj necesita el mismo número.', 'Lass 4455, wenn du es nicht besser weißt — die Uhr-App braucht dieselbe Nummer.', 'Laisse 4455 sauf si tu sais mieux — l’app de la montre a besoin du même numéro.', 'Deixa 4455 a não ser que saibas melhor — a app do relógio precisa do mesmo número.')
_tr7('settings.hr_critical_bpm_label', '助けに入る心拍', '介入的心率', 'Пульс, при котором помочь', 'Pulso al que intervenir', 'Puls, ab dem eingegriffen wird', 'Pouls auquel intervenir', 'Pulso a que intervir')
_tr7('settings.hr_critical_bpm_hint_new', 'この上限からアプリが負荷を計算します。低くするほど心拍が早く「高い」とみなされます。越えた瞬間ではなく、負荷が十分に長く高いままのときに声をかけます。', '应用会根据这个上限计算负荷。设得越低，你的心率越早被算作偏高。它不会在刚越过时就出声，而是在负荷持续偏高足够久时才提醒。', 'Из этого потолка приложение считает нагрузку — чем ниже ты его поставишь, тем раньше пульс считается высоким. Оно отзовётся, когда нагрузка продержится высоко достаточно долго, а не сразу при переходе.', 'La app calcula tu carga a partir de este techo: cuanto más bajo lo pongas, antes contará tu pulso como alto. Habla cuando la carga se mantiene alta el tiempo suficiente, no en cuanto lo cruzas.', 'Aus dieser Obergrenze berechnet die App deine Belastung — je niedriger du sie setzt, desto früher gilt dein Puls als hoch. Sie meldet sich, wenn die Belastung lange genug oben bleibt, nicht schon beim Überschreiten.', 'L’app calcule ta charge à partir de ce plafond : plus tu le baisses, plus vite ton pouls compte comme élevé. Elle parle quand la charge reste haute assez longtemps, pas dès que tu le franchis.', 'A app calcula a tua carga a partir deste limite — quanto mais baixo o puseres, mais cedo o teu pulso conta como alto. Fala quando a carga se mantém alta tempo suficiente, não assim que o ultrapassas.')
_tr7('settings.hr_enable_switch', '時計から心拍を受け取る', '接收手表的心率', 'Слушать пульс с часов', 'Escuchar el pulso del reloj', 'Puls von der Uhr empfangen', 'Écouter le pouls de la montre', 'Ouvir o pulso do relógio')
_tr7('settings.cooldown', 'リマインダーの間隔', '提醒之间的间隔', 'Пауза между напоминаниями', 'Pausa entre recordatorios', 'Pause zwischen Erinnerungen', 'Pause entre les rappels', 'Pausa entre lembretes')
_tr7('settings.cooldown_sub', 'アプリがまた話すまでの最短時間。短ければ頻繁に、長ければゲームに集中させてくれる。', '应用再次开口前的最短时间。间隔短会经常提醒，长则让你安心玩。', 'Кратчайшее время, прежде чем приложение заговорит снова. Короткая пауза напоминает часто, длинная даёт спокойно играть.', 'El tiempo mínimo antes de que la app vuelva a hablar. Una pausa corta recuerda a menudo; una larga te deja jugar.', 'Die kürzeste Zeit, bis die App wieder spricht. Eine kurze Pause erinnert oft, eine lange lässt dich spielen.', 'Le temps minimum avant que l’app reparle. Une pause courte rappelle souvent, une longue te laisse jouer.', 'O tempo mínimo antes de o app falar outra vez. Uma pausa curta lembra muitas vezes, uma longa deixa-te jogar.')
_tr7('settings.volume', '音量', '音量', 'Громкость', 'Volumen', 'Lautstärke', 'Volume', 'Volume')
_tr7('settings.volume_sub', 'リマインダーだけに効く。ゲームの音量は変わらない。', '只影响提醒。不会改变游戏音量。', 'Действует только на напоминания. Громкость игры не меняется.', 'Solo afecta a los recordatorios. No cambia el volumen del juego.', 'Gilt nur für die Erinnerungen. Die Spiellautstärke ändert sich nicht.', 'Ne concerne que les rappels. Ne change pas le volume du jeu.', 'Só se aplica aos lembretes. Não muda o volume do jogo.')
_tr7('settings.balance', '効果音 ↔ 音声のバランス', '音效 ↔ 语音 比例', 'Баланс звук ↔ голос', 'Mezcla sonido ↔ voz', 'Verhältnis Ton ↔ Stimme', 'Équilibre son ↔ voix', 'Mistura som ↔ voz')
_tr7('settings.balance_sub', '音量を効果音と話し声にどう配分するか。左は効果音寄り、右は音声寄り。', '音量在音效和语音之间如何分配。偏左更偏音效，偏右更偏语音。', 'Как громкость делится между звуковым эффектом и голосом. Влево — больше звука, вправо — больше голоса.', 'Cómo se reparte el volumen entre el efecto de sonido y la voz. A la izquierda manda el sonido; a la derecha, la voz.', 'Wie sich die Lautstärke zwischen Soundeffekt und Sprachzeile aufteilt. Links führt der Ton, rechts die Stimme.', 'Comment le volume se répartit entre l’effet sonore et la voix. À gauche le son domine, à droite la voix.', 'Como o volume se divide entre o efeito sonoro e a voz. À esquerda manda o som, à direita a voz.')
_tr7('settings.balance_center', '半々', '各半', 'поровну', 'a partes iguales', 'halb-halb', 'à parts égales', 'a meias')
_tr7('settings.balance_sfx', '効果音', '音效', 'звук', 'sonido', 'Ton', 'son', 'som')
_tr7('settings.balance_tts', '音声', '语音', 'голос', 'voz', 'Stimme', 'voix', 'voz')
_tr7('settings.overlap', 'セリフが重なってもよい', '语音可以重叠', 'Реплики могут накладываться', 'Las frases pueden solaparse', 'Sprachzeilen dürfen sich überlappen', 'Les répliques peuvent se chevaucher', 'As frases podem sobrepor-se')
_tr7('settings.overlap_sub', 'オフ：セリフは順番待ち。オン：同時に鳴ってよい — トリガーが近くで重なるときに便利。', '关闭：语音会排队。开启：可以同时响 — 当多个触发器挨得很近时很有用。', 'Выключено: реплики ждут друг друга. Включено: могут звучать одновременно — удобно, когда триггеры срабатывают подряд.', 'Apagado: las frases se esperan. Encendido: pueden sonar a la vez, útil cuando varios disparadores caen juntos.', 'Aus: Sprachzeilen warten aufeinander. An: sie können gleichzeitig klingen — praktisch, wenn mehrere Trigger dicht beieinander feuern.', 'Désactivé : les répliques s’attendent. Activé : elles peuvent sonner en même temps — pratique quand plusieurs déclencheurs se suivent.', 'Desligado: as frases esperam umas pelas outras. Ligado: podem soar ao mesmo tempo — útil quando vários gatilhos disparam juntos.')
_tr7('settings.engine', '音声の生成元', '语音来源', 'Голос берётся из', 'La voz viene de', 'Stimme kommt von', 'La voix vient de', 'A voz vem de')
_tr7('settings.engine_sub', '自然な音声のほうがよく聞こえるが、セリフをネット経由で先に用意する必要がある。Windows の音声はいつでもすぐ使える。', '自然语音听起来更好，但需要先通过网络准备好台词。Windows 语音随时可用。', 'Естественный голос звучит лучше, но реплики сперва нужно подготовить через интернет. Голос Windows доступен сразу и всегда.', 'La voz natural suena mejor, pero primero tiene que preparar las frases por internet. La voz de Windows está siempre disponible al instante.', 'Die natürliche Stimme klingt besser, muss die Zeilen aber erst übers Internet vorbereiten. Die Windows-Stimme ist immer sofort da.', 'La voix naturelle sonne mieux mais doit d’abord préparer les répliques via internet. La voix Windows est toujours disponible immédiatement.', 'A voz natural soa melhor, mas tem de preparar as frases pela internet primeiro. A voz do Windows está sempre disponível de imediato.')
_tr7('settings.voice', '音声', '语音', 'Голос', 'Voz', 'Stimme', 'Voix', 'Voz')
_tr7('settings.voice_sub', '自分の音声を持たないすべてのトリガーに使われる。', '用于所有没有设置自己语音的触发器。', 'Используется для каждого триггера, у которого нет своего голоса.', 'Se usa para cada disparador que no tenga voz propia.', 'Wird für jeden Trigger verwendet, der keine eigene Stimme hat.', 'Utilisée pour chaque déclencheur qui n’a pas sa propre voix.', 'Usada para cada gatilho que não tenha voz própria.')
_tr7('settings.rate', '話す速さ', '语速', 'Скорость речи', 'Velocidad del habla', 'Sprechtempo', 'Vitesse de parole', 'Velocidade da fala')
_tr7('settings.rate_sub', 'マイナスで遅く、プラスで速く。ストレス下ではゆっくりのほうが聞き取りやすい。', '负数变慢，正数变快。压力大时慢一点更容易听懂。', 'Минус замедляет, плюс ускоряет. Под стрессом медленную речь легче воспринимать.', 'El menos la ralentiza y el más la acelera. Bajo estrés se sigue mejor un habla más lenta.', 'Minus verlangsamt, Plus beschleunigt. Unter Stress folgt man langsamerer Sprache leichter.', 'Le moins ralentit, le plus accélère. Sous stress, une parole plus lente est plus facile à suivre.', 'O menos abranda, o mais acelera. Sob stress, fala mais lenta é mais fácil de seguir.')
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
_tr7('settings.audio_reset', '推奨値に戻す', '恢复推荐值', 'Вернуть рекомендуемые', 'Restaurar los recomendados', 'Empfohlene wiederherstellen', 'Rétablir les valeurs recommandées', 'Repor os recomendados')
_tr7('settings.audio_reset_sub', '音量、バランス、話す速さ、間隔、重なりがアプリの初期値に戻る。選んだ音声はそのまま。', '音量、比例、语速、间隔和重叠都会回到应用出厂时的值。你选的语音会保留。', 'Громкость, баланс, скорость речи, пауза и наложение вернутся к значениям, с которыми пришло приложение. Выбранный голос останется.', 'El volumen, la mezcla, la velocidad del habla, la pausa y el solapamiento vuelven a los valores de fábrica. Tu voz elegida se mantiene.', 'Lautstärke, Mischung, Sprechtempo, Pause und Überlappung gehen zurück auf die Werte, mit denen die App kam. Deine gewählte Stimme bleibt.', 'Le volume, l’équilibre, la vitesse de parole, la pause et le chevauchement reviennent aux valeurs d’origine. Ta voix choisie reste.', 'O volume, a mistura, a velocidade da fala, a pausa e a sobreposição voltam aos valores de origem. A voz escolhida mantém-se.')
_tr7('settings.audio_reset_btn', '戻す', '恢复', 'Вернуть', 'Restaurar', 'Zurücksetzen', 'Rétablir', 'Repor')
_tr7('settings.look_title', '見た目と言語', '外观与语言', 'Вид и язык', 'Aspecto e idioma', 'Aussehen und Sprache', 'Apparence et langue', 'Aspeto e idioma')
_tr7('settings.theme', 'カラーテーマ', '配色主题', 'Цветовая тема', 'Tema de color', 'Farbthema', 'Thème de couleur', 'Tema de cor')
_tr7('settings.theme_sub', 'Aizome は藍、Sumi は墨に金。切り替えは即時 — 両方ためしてみて。', 'Aizome 是靛蓝，Sumi 是墨色配金。切换是即时的 — 两个都试试。', 'Aizome — индиго, Sumi — тушь с золотом. Переключается мгновенно — попробуй обе.', 'Aizome es índigo; Sumi, tinta con oro. Cambia al instante: prueba las dos.', 'Aizome ist Indigo, Sumi ist Tusche mit Gold. Der Wechsel ist sofort — probier beide.', 'Aizome est indigo, Sumi est encre et or. Le changement est instantané — essaie les deux.', 'Aizome é índigo, Sumi é tinta com ouro. Muda instantaneamente — experimenta as duas.')
_tr7('settings.language', '言語', '语言', 'Язык', 'Idioma', 'Sprache', 'Langue', 'Idioma')
_tr7('settings.language_sub', 'サンプルのセリフの言語も変わる。', '示例台词的语言也会一起改变。', 'Меняется и язык образцовых фраз.', 'También cambia el idioma de las frases de ejemplo.', 'Ändert auch die Sprache der Beispielsätze.', 'Change aussi la langue des phrases d’exemple.', 'Muda também o idioma das frases de exemplo.')
_tr7('settings.behaviour_title', 'ふるまい', '行为', 'Поведение', 'Comportamiento', 'Verhalten', 'Comportement', 'Comportamento')
_tr7('settings.guide_title', 'ガイド', '指南', 'Справочник', 'Guía', 'Leitfaden', 'Guide', 'Guia')
_tr7('settings.guide_row', 'なぜ顎、重心、呼吸なのか', '为什么是下巴、重心和呼吸', 'Почему челюсть, центр тяжести и дыхание', 'Por qué mandíbula, centro y respiración', 'Warum Kiefer, Schwerpunkt und Atem', 'Pourquoi mâchoire, ancrage et souffle', 'Porquê maxilar, centro e respiração')
_tr7('settings.guide_sub', 'リマインダーごとの短い説明 — 体で何が起きていて、なぜ効くのか。', '每个提醒的简短说明 — 身体里发生了什么，以及为什么有效。', 'Короткая заметка о каждом напоминании — что происходит в теле и почему это работает.', 'Una nota breve sobre cada recordatorio: qué pasa en el cuerpo y por qué funciona.', 'Eine kurze Notiz zu jeder Erinnerung — was im Körper passiert und warum es wirkt.', 'Une note brève sur chaque rappel — ce qui se passe dans le corps et pourquoi ça marche.', 'Uma nota curta sobre cada lembrete — o que acontece no corpo e porque funciona.')
_tr7('settings.tour_row', 'アプリのツアー', '应用导览', 'Экскурсия по приложению', 'Recorrido por la app', 'App-Tour', 'Visite de l’app', 'Visita ao app')
_tr7('settings.tour_row_at', 'アプリのツアー — ステップ {n} / {total}', '应用导览 — 第 {n} 步，共 {total} 步', 'Экскурсия по приложению — шаг {n} из {total}', 'Recorrido por la app: paso {n} de {total}', 'App-Tour — Schritt {n} von {total}', 'Visite de l’app — étape {n} sur {total}', 'Visita ao app — passo {n} de {total}')
_tr7('settings.tour_sub', 'どこに何があるかの短い案内。', '简短介绍东西都在哪儿。', 'Короткая экскурсия по тому, где что находится.', 'Un recorrido breve por dónde está cada cosa.', 'Eine kurze Tour, wo was ist.', 'Une brève visite de l’endroit où se trouve quoi.', 'Uma visita curta a onde está o quê.')
_tr7('settings.tour_btn', 'ツアーを始める', '开始导览', 'Начать экскурсию', 'Empezar el recorrido', 'Tour starten', 'Démarrer la visite', 'Iniciar a visita')
_tr7('settings.tour_resume', '続ける', '继续', 'Продолжить', 'Continuar', 'Fortsetzen', 'Continuer', 'Continuar')
_tr7('dialog.timing_title', 'タイミング', '时机', 'Тайминг', 'Tiempos', 'Timing', 'Rythme', 'Tempo')
_tr7('settings.audio_timing_title', 'タイミング', '时机', 'Тайминг', 'Tiempos', 'Timing', 'Rythme', 'Tempo')
_tr7('settings.speed_normal', 'ふつう', '正常', 'нормально', 'normal', 'normal', 'normal', 'normal')
_tr7('history.title', 'セッション履歴', '记录历史', 'История сессий', 'Historial de sesiones', 'Sitzungsverlauf', 'Historique des séances', 'Histórico de sessões')
_tr7('history.subtitle', '心拍つきのセッション（1分以上）はすべてここに保存される。指標は素の心拍から — HRV ではない。', '每一次带心率的记录（至少一分钟）都会保存在这里。指标来自纯心率 — 不是 HRV。', 'Каждая сессия с пульсом (не короче минуты) сохраняется здесь. Показатели — из чистого пульса, не из HRV.', 'Cada sesión con pulso (de al menos un minuto) se guarda aquí. Las métricas salen del pulso puro, no de la HRV.', 'Jede Sitzung mit Puls (mindestens eine Minute) wird hier gespeichert. Die Kennzahlen stammen aus dem reinen Puls — nicht aus HRV.', 'Chaque séance avec pouls (au moins une minute) est enregistrée ici. Les mesures viennent du pouls brut — pas de la VFC.', 'Cada sessão com pulso (pelo menos um minuto) é guardada aqui. As métricas vêm do pulso puro — não de HRV.')
_tr7('history.empty', 'まだセッションはない。「ゲーム中」で心拍センサーを入れ、1分以上プレイすれば、止めたときにここに出る。', '还没有记录。在“游戏中”打开心率传感器，玩上至少一分钟，停止后这里就会出现。', 'Сессий пока нет. Включи датчик пульса в «В игре», поиграй хотя бы минуту — после остановки сессия появится здесь.', 'Todavía no hay sesiones. Activa el sensor de pulso en «En el juego», juega al menos un minuto y la sesión aparecerá aquí al parar.', 'Noch keine Sitzungen. Schalte den Pulssensor unter „Im Spiel“ ein, spiel mindestens eine Minute — nach dem Stoppen erscheint die Sitzung hier.', 'Pas encore de séances. Active le capteur de pouls dans « En jeu », joue au moins une minute et la séance apparaîtra ici après l’arrêt.', 'Ainda não há sessões. Liga o sensor de pulso em «No jogo», joga pelo menos um minuto e a sessão aparece aqui quando parares.')
_tr7('history.insights_title', 'アプリが気づいたこと', '应用注意到的事', 'Что заметило приложение', 'Lo que la app ha notado', 'Was der App aufgefallen ist', 'Ce que l’app a remarqué', 'O que o app reparou')
_tr7('history.insights_note', '履歴全体からバックグラウンドで計算。観察とヒントであって、診断ではない。', '在后台从你的全部历史计算而来。是观察和建议，不是诊断。', 'Считается в фоне по всей твоей истории. Это наблюдения и подсказки, а не диагнозы.', 'Se calcula en segundo plano a partir de todo tu historial. Son observaciones y consejos, no diagnósticos.', 'Wird im Hintergrund aus deinem gesamten Verlauf berechnet. Beobachtungen und Tipps, keine Diagnosen.', 'Calculé en arrière-plan à partir de tout ton historique. Des observations et des conseils, pas des diagnostics.', 'Calculado em segundo plano a partir de todo o teu histórico. São observações e dicas, não diagnósticos.')
_tr7('history.analysis_running', '履歴を分析中…', '正在分析历史…', 'Анализирую историю…', 'Analizando el historial…', 'Verlauf wird analysiert…', 'Analyse de l’historique…', 'A analisar o histórico…')
_tr7('history.analysis_stamp', '{when} の分析', '{when} 的分析', 'Анализ от {when}', 'Análisis de {when}', 'Analyse vom {when}', 'Analyse du {when}', 'Análise de {when}')
_tr7('history.recompute', '再計算', '重新计算', 'Пересчитать', 'Recalcular', 'Neu berechnen', 'Recalculer', 'Recalcular')
_tr7('history.trend_title', 'セッションをまたいだ推移', '跨记录的趋势', 'Динамика по сессиям', 'Evolución entre sesiones', 'Verlauf über die Sitzungen', 'Évolution entre séances', 'Evolução entre sessões')
_tr7('history.trend_baseline', 'セッションごとの安静時ベースライン（BPM） — 古いものが左', '每次记录的静息基线（BPM）— 越旧越靠左', 'Базовая линия покоя (уд/мин) по сессиям — старые слева', 'Línea base en reposo (ppm) por sesión: las más antiguas a la izquierda', 'Ruhebasislinie (S/min) pro Sitzung — die ältesten links', 'Ligne de base au repos (bpm) par séance — les plus anciennes à gauche', 'Linha de base em repouso (bpm) por sessão — as mais antigas à esquerda')
_tr7('history.trend_avg', 'セッションごとの平均心拍（BPM） — 古いものが左', '每次记录的平均心率（BPM）— 越旧越靠左', 'Средний пульс (уд/мин) по сессиям — старые слева', 'Pulso medio (ppm) por sesión: las más antiguas a la izquierda', 'Durchschnittspuls (S/min) pro Sitzung — die ältesten links', 'Pouls moyen (bpm) par séance — les plus anciennes à gauche', 'Pulso médio (bpm) por sessão — as mais antigas à esquerda')
_tr7('history.trend_delta', '{first} → {last} BPM、推移 {slope:+.1f} BPM/週', '{first} → {last} BPM，趋势 {slope:+.1f} BPM/周', '{first} → {last} уд/мин, тренд {slope:+.1f} уд/мин в неделю', '{first} → {last} ppm, tendencia {slope:+.1f} ppm/semana', '{first} → {last} S/min, Trend {slope:+.1f} S/min pro Woche', '{first} → {last} bpm, tendance {slope:+.1f} bpm/semaine', '{first} → {last} bpm, tendência {slope:+.1f} bpm/semana')
_tr7('history.trend_need_more', 'セッションがまだ近すぎて推移が出せない — 数日たってからまた見て。', '记录之间还太密集，看不出趋势 — 过几天再来看。', 'Сессии пока слишком близко друг к другу для тренда — загляни через несколько дней.', 'Las sesiones están aún demasiado juntas para una tendencia: vuelve dentro de unos días.', 'Die Sitzungen liegen für einen Trend noch zu dicht beieinander — schau in ein paar Tagen wieder rein.', 'Les séances sont encore trop rapprochées pour une tendance — reviens dans quelques jours.', 'As sessões ainda estão demasiado juntas para uma tendência — volta daqui a uns dias.')
_tr7('history.empty_period', 'この期間にはまだ何もない。', '这个时间段还没有内容。', 'В этом периоде пока ничего.', 'Todavía no hay nada en este periodo.', 'In diesem Zeitraum noch nichts.', 'Rien dans cette période pour l’instant.', 'Ainda nada neste período.')
_tr7('history.period.hour', '時間', '小时', 'Час', 'Hora', 'Stunde', 'Heure', 'Hora')
_tr7('history.period.day', '日', '天', 'День', 'Día', 'Tag', 'Jour', 'Dia')
_tr7('history.period.week', '週', '周', 'Неделя', 'Semana', 'Woche', 'Semaine', 'Semana')
_tr7('history.period.month', '月', '月', 'Месяц', 'Mes', 'Monat', 'Mois', 'Mês')
_tr7('history.period.year', '年', '年', 'Год', 'Año', 'Jahr', 'Année', 'Ano')
_tr7('history.pick_metric', '指標', '指标', 'Метрика', 'Métrica', 'Kennzahl', 'Mesure', 'Métrica')
_tr7('history.pick_period', '期間', '时间段', 'Период', 'Periodo', 'Zeitraum', 'Période', 'Período')
_tr7('history.band_label', 'あなたのふつうの幅', '你的常见范围', 'твой обычный диапазон', 'tu rango habitual', 'dein üblicher Bereich', 'ta plage habituelle', 'o teu intervalo habitual')
_tr7('history.unit.hrr', '1分あたりの BPM', '每分钟 BPM', 'BPM за минуту', 'BPM por minuto', 'BPM pro Minute', 'BPM par minute', 'BPM por minuto')
_tr7('history.unit.over', '分', '分钟', 'минуты', 'minutos', 'Minuten', 'minutes', 'minutos')
_tr7('history.unit.peak', '0〜100 のうち', '满分 100', 'из 0–100', 'de 0–100', 'von 0–100', 'sur 0–100', 'de 0–100')
_tr7('history.sessions_title', 'セッション', '记录', 'Сессии', 'Sesiones', 'Sitzungen', 'Séances', 'Sessões')
_tr7('history.sessions_count', '{n} セッション', '{n} 次记录', 'Сессий: {n}', '{n} sesiones', '{n} Sitzungen', '{n} séances', '{n} sessões')
_tr7('history.col_date', '日付', '日期', 'Дата', 'Fecha', 'Datum', 'Date', 'Data')
_tr7('history.col_duration', '長さ', '时长', 'Длина', 'Duración', 'Länge', 'Durée', 'Duração')
_tr7('history.col_avg', '平均', '平均', 'Среднее', 'Media', 'Schnitt', 'Moyenne', 'Média')
_tr7('history.col_over', 'しきい値超え', '超阈', 'Выше порога', 'Sobre el límite', 'Über der Grenze', 'Au-dessus du seuil', 'Acima do limite')
_tr7('history.col_triggers', '呼吸', '呼吸', 'Дыхание', 'Respiración', 'Atmung', 'Respiration', 'Respiração')
_tr7('history.col_peak', '負荷のピーク', '负荷峰值', 'Пик нагрузки', 'Pico de carga', 'Last-Spitze', 'Pic de charge', 'Pico de carga')
_tr7('history.info_more', 'ⓘ どういう意味', 'ⓘ 这是什么意思', 'ⓘ что это значит', 'ⓘ qué significa', 'ⓘ was das bedeutet', 'ⓘ ce que ça veut dire', 'ⓘ o que significa')
_tr7('history.info_less', 'ⓘ 隠す', 'ⓘ 隐藏', 'ⓘ скрыть', 'ⓘ ocultar', 'ⓘ ausblenden', 'ⓘ masquer', 'ⓘ esconder')
_tr7('history.science_title', 'なぜ効くのか', '为什么有效', 'Почему это работает', 'Por qué funciona', 'Warum es wirkt', 'Pourquoi ça marche', 'Porque funciona')
_tr7('history.science_intro', 'Zanshin は健康のために心拍を測っているのではない — いつ落ち着く手助けをすべきかを知るために測っている。その土台になっている科学はこれ：', 'Zanshin 测心率不是为了健康 — 而是为了知道什么时候该帮你平静下来。它依据的科学如下：', 'Zanshin меряет пульс не ради здоровья — а чтобы знать, когда помочь тебе успокоиться. Вот наука, на которой это стоит:', 'Zanshin no mide tu pulso por salud: lo mide para saber cuándo ayudarte a calmarte. Esta es la ciencia en la que se apoya:', 'Zanshin misst deinen Puls nicht für die Gesundheit — sondern um zu wissen, wann es dir beim Runterkommen helfen soll. Darauf stützt es sich:', 'Zanshin ne mesure pas ton pouls pour la santé — il le mesure pour savoir quand t’aider à te calmer. Voici la science sur laquelle il s’appuie :', 'O Zanshin não mede o teu pulso por saúde — mede-o para saber quando te ajudar a acalmar. É nesta ciência que assenta:')
_tr7('history.science_hrv_note', 'HRV のリンクは心拍とストレスの文脈として置いてある — アプリは HRV を測らない（拍と拍の間隔が必要で、時計はそれをこの形では送らない）。', 'HRV 的链接放在这里只是关于心率与压力的背景 — 本应用不测量 HRV（它需要心跳间隔，而手表并不以这种方式发送）。', 'Ссылки про HRV здесь как контекст о пульсе и стрессе — приложение HRV не измеряет (для него нужны интервалы между ударами, а часы их так не присылают).', 'Los enlaces sobre HRV están aquí como contexto sobre pulso y estrés: la app no mide HRV (necesita intervalos latido a latido, que el reloj no envía así).', 'Die HRV-Links stehen hier als Kontext zu Puls und Stress — die App misst kein HRV (dafür bräuchte es Schlag-zu-Schlag-Intervalle, die die Uhr so nicht sendet).', 'Les liens sur la VFC sont ici en contexte sur le pouls et le stress — l’app ne mesure pas la VFC (il faudrait les intervalles entre battements, que la montre n’envoie pas ainsi).', 'Os links sobre HRV estão aqui como contexto sobre pulso e stress — o app não mede HRV (precisaria de intervalos batimento a batimento, que o relógio não envia assim).')
_tr7('history.export_extra', 'あわせて保存されました:\\n{files}', '同时保存了:\\n{files}', 'Вместе с этим сохранено:\\n{files}', 'Junto a esto se guardó:\\n{files}', 'Zusätzlich gespeichert:\\n{files}', 'Enregistré également :\\n{files}', 'Também foi guardado:\\n{files}')
_tr7('history.export_col.longest_above_s', 'しきい値超えの最長 (秒)', '超过阈值最长 (秒)', 'дольше всего выше порога (с)', 'más largo sobre el umbral (s)', 'längste Zeit über Schwelle (s)', 'plus long au-dessus du seuil (s)', 'mais longo acima do limiar (s)')
_tr7('history.export_col.above_runs', 'しきい値超えの回数', '超阈值次数', 'участков выше порога', 'tramos sobre el umbral', 'Abschnitte über Schwelle', 'segments au-dessus du seuil', 'trechos acima do limiar')
_tr7('history.export_col.cancelled_dip', '低下で中断', '因回落中断', 'отменено спадом', 'cancelado por caída', 'durch Abfall abgebrochen', 'annulé par une baisse', 'cancelado por queda')
_tr7('history.export_col.cancelled_gap', '欠測で中断', '因断连中断', 'отменено пропаданием', 'cancelado por corte', 'durch Ausfall abgebrochen', 'annulé par une coupure', 'cancelado por falha')
_tr7('history.export_col.hold_s', '必要な継続 (秒)', '所需持续 (秒)', 'нужное удержание (с)', 'retención necesaria (s)', 'nötiges Halten (s)', 'maintien requis (s)', 'retenção necessária (s)')
_tr7('history.export_col.context', '文脈', '情境', 'контекст', 'contexto', 'Kontext', 'contexte', 'contexto')
_tr7('history.effect_title', 'どの合図が効くか', '哪种提醒有效', 'Какая подсказка помогает', 'Qué aviso funciona', 'Welcher Hinweis wirkt', 'Quel rappel fonctionne', 'Que aviso funciona')
_tr7('history.effect_hint', '合図のあとの心拍の動き。中央より左は下がったという意味です。細い線は本当の値がありそうな範囲で、中央をまたいでいるあいだは逆の可能性もあります。', '提醒之后心率的变化。在中线左边表示下降了。细线是真实值可能所在的范围 —— 只要它跨过中线，差异也可能是相反的。', 'Как менялся пульс после подсказки. Левее центра — значит снизился. Тонкая линия — диапазон, в котором, скорее всего, лежит истинное значение; пока он пересекает центр, разница может быть и обратной.', 'Cómo se movió tu pulso tras el aviso. A la izquierda del centro significa que bajó. La línea fina es el rango donde probablemente está el valor real: mientras cruce el centro, la diferencia podría ir en cualquier sentido.', 'Wie sich dein Puls nach dem Hinweis bewegt hat. Links von der Mitte heißt gesunken. Die dünne Linie ist der Bereich, in dem der wahre Wert wohl liegt — solange sie die Mitte schneidet, kann der Unterschied auch umgekehrt sein.', 'Comment ton pouls a évolué après le rappel. À gauche du centre : il a baissé. La ligne fine est la plage où se situe probablement la vraie valeur — tant qu’elle croise le centre, l’écart peut aller dans les deux sens.', 'Como o teu pulso se moveu depois do aviso. À esquerda do centro significa que desceu. A linha fina é o intervalo onde o valor real provavelmente está — enquanto cruzar o centro, a diferença pode ir nos dois sentidos.')
_tr7('history.effect_few', '今は {n} 件 — 判断には足りません', '目前 {n} 次 — 还不足以下结论', 'пока {n} — мало для выводов', 'por ahora {n}: pocos para afirmar nada', 'bisher {n} — zu wenig für eine Aussage', 'pour l’instant {n} — trop peu pour conclure', 'por agora {n} — poucos para afirmar')
_tr7('history.effect_empty', '測定できる合図がまだ一度も鳴っていません。', '还没有任何可供测量的提醒响起。', 'Пока не прозвучала ни одна подсказка, которую можно измерить.', 'Todavía no ha sonado ningún aviso que se pueda medir.', 'Es ist noch kein Hinweis erklungen, den man messen könnte.', 'Aucun rappel mesurable n’a encore retenti.', 'Ainda não soou nenhum aviso que se possa medir.')
_tr7('cue.category.grounding', '重心', '重心', 'опора', 'centro', 'Schwerpunkt', 'ancrage', 'centro')
_tr7('cue.category.jaw', '顎', '下颌', 'челюсть', 'mandíbula', 'Kiefer', 'mâchoire', 'mandíbula')
_tr7('cue.category.release', '脱力', '放松', 'расслабление', 'soltar', 'Lösen', 'relâchement', 'soltar')
_tr7('cue.category.breath', '呼吸', '呼吸', 'дыхание', 'respiración', 'Atem', 'souffle', 'respiração')
_tr7('history.rhythm_title', '続けぐあい', '规律性', 'Регулярность', 'Constancia', 'Regelmäßigkeit', 'Régularité', 'Regularidade')
_tr7('history.days_played', 'セッションのあった日 · 年', '有记录的天数 · 年', 'Дней с сессией · год', 'Días con sesión · año', 'Tage mit Sitzung · Jahr', 'Jours avec séance · an', 'Dias com sessão · ano')
_tr7('history.grid_less', '少ない', '较少', 'меньше', 'menos', 'weniger', 'moins', 'menos')
_tr7('history.grid_more', '多い', '较多', 'больше', 'más', 'mehr', 'plus', 'mais')
_tr7('history.detail_title', 'セッションを間近で', '近看一次记录', 'Одна сессия вблизи', 'Una sesión de cerca', 'Eine Sitzung aus der Nähe', 'Une séance de près', 'Uma sessão de perto')
_tr7('history.detail_peak', '最高心拍', '最高心率', 'Самый высокий пульс', 'Pulso más alto', 'Höchster Puls', 'Pouls le plus haut', 'Pulso mais alto')
_tr7('history.detail_hrr', '回復', '恢复', 'Восстановление', 'Recuperación', 'Erholung', 'Récupération', 'Recuperação')
_tr7('history.detail_breath', '呼吸', '呼吸', 'Дыхание', 'Respiración', 'Atmung', 'Respiration', 'Respiração')
_tr7('history.detail_hint', '表の行をクリックすると、別のセッションを見られる。', '点击表格中的某一行即可查看另一次记录。', 'Нажми на строку в таблице, чтобы посмотреть другую сессию.', 'Haz clic en una fila de la tabla para ver otra sesión.', 'Klick auf eine Zeile in der Tabelle, um eine andere Sitzung anzusehen.', 'Clique sur une ligne du tableau pour voir une autre séance.', 'Clica numa linha da tabela para veres outra sessão.')
_tr7('history.detail_empty', 'まだセッションがない — ここにその曲線が出る。', '还没有记录 — 它的曲线会显示在这里。', 'Сессий пока нет — здесь появится её кривая.', 'Aún no hay sesiones: aquí aparecerá su curva.', 'Noch keine Sitzung — hier erscheint ihre Kurve.', 'Pas encore de séance — sa courbe apparaîtra ici.', 'Ainda não há sessão — a sua curva aparece aqui.')
_tr7('history.detail_no_curve', 'このセッションは古いバージョンのもので、曲線はもう復元できない。新しいセッションは保存している。', '这次记录来自旧版本，曲线已无法还原。新的记录会保存曲线。', 'Эта сессия из более старой версии, её кривую уже не восстановить. Новые сессии её сохраняют.', 'Esta sesión viene de una versión anterior, así que su curva ya no se puede reconstruir. Las nuevas sí la guardan.', 'Diese Sitzung stammt aus einer älteren Version, ihre Kurve lässt sich nicht mehr rekonstruieren. Neue Sitzungen speichern sie.', 'Cette séance vient d’une version plus ancienne, sa courbe ne peut plus être reconstituée. Les nouvelles la conservent.', 'Esta sessão vem de uma versão mais antiga, por isso a curva já não pode ser reconstruída. As novas guardam-na.')
_tr7('history.export_btn', '表にエクスポート', '导出为表格', 'Экспорт в таблицу', 'Exportar a una hoja de cálculo', 'In eine Tabelle exportieren', 'Exporter vers un tableur', 'Exportar para uma folha de cálculo')
_tr7('history.export_filetype', 'Excel 用の表（CSV）', 'Excel 表格（CSV）', 'Таблица для Excel (CSV)', 'Hoja de cálculo de Excel (CSV)', 'Excel-Tabelle (CSV)', 'Tableur Excel (CSV)', 'Folha de cálculo do Excel (CSV)')
_tr7('history.export_local', '心拍もセッションも設定も、このパソコンから出ていかない — アプリはどこにも送らないし、ファイルの置き場所は自分で選ぶ。', '心率、记录和设置都不会离开这台电脑 — 应用不会把它们发到任何地方，文件存到哪里由你决定。', 'Твой пульс, сессии и настройки никогда не покидают этот компьютер — приложение никуда их не отправляет, а место файла выбираешь ты.', 'Tu pulso, tus sesiones y tus ajustes nunca salen de este ordenador: la app no los envía a ningún sitio y tú eliges dónde va el archivo.', 'Dein Puls, deine Sitzungen und Einstellungen verlassen diesen Rechner nie — die App sendet sie nirgendwohin, und du wählst, wohin die Datei kommt.', 'Ton pouls, tes séances et tes réglages ne quittent jamais cet ordinateur — l’app ne les envoie nulle part, et c’est toi qui choisis où va le fichier.', 'O teu pulso, as sessões e as definições nunca saem deste computador — o app não os envia para lado nenhum e és tu que escolhes onde fica o ficheiro.')
_tr7('history.export_empty', 'エクスポートするものがまだない — まず心拍センサーつきでセッションをこなして。', '还没有可导出的内容 — 先带着心率传感器玩一次。', 'Пока нечего экспортировать — сначала проведи сессию с датчиком пульса.', 'Todavía no hay nada que exportar: juega antes una sesión con el sensor de pulso.', 'Noch nichts zum Exportieren — spiel zuerst eine Sitzung mit dem Pulssensor.', 'Rien à exporter pour l’instant — joue d’abord une séance avec le capteur de pouls.', 'Ainda não há nada para exportar — joga primeiro uma sessão com o sensor de pulso.')
_tr7('history.export_done', '{n} セッションを {path} に保存した。', '已把 {n} 次记录保存到 {path}。', 'Сохранено сессий: {n} — в {path}.', 'Se guardaron {n} sesiones en {path}.', '{n} Sitzungen in {path} gespeichert.', '{n} séances enregistrées dans {path}.', 'Guardadas {n} sessões em {path}.')
_tr7('history.export_failed', 'エクスポートに失敗した：{err}', '导出失败：{err}', 'Экспорт не удался: {err}', 'La exportación falló: {err}', 'Export fehlgeschlagen: {err}', 'L’export a échoué : {err}', 'A exportação falhou: {err}')
_tr7('history.export_col.date', '日付', '日期', 'Дата', 'Fecha', 'Datum', 'Date', 'Data')
_tr7('history.export_col.start', '開始', '开始', 'Начало', 'Inicio', 'Beginn', 'Début', 'Início')
_tr7('history.export_col.duration_min', '長さ（分）', '时长（分钟）', 'Длина (мин)', 'Duración (min)', 'Länge (Min)', 'Durée (min)', 'Duração (min)')
_tr7('history.export_col.avg_bpm', '平均 BPM', '平均 BPM', 'Средний BPM', 'BPM medio', 'Durchschnitts-BPM', 'BPM moyen', 'BPM médio')
_tr7('history.export_col.min_bpm', '最低 BPM', '最低 BPM', 'Минимальный BPM', 'BPM mínimo', 'Niedrigster BPM', 'BPM le plus bas', 'BPM mais baixo')
_tr7('history.export_col.max_bpm', '最高 BPM', '最高 BPM', 'Максимальный BPM', 'BPM máximo', 'Höchster BPM', 'BPM le plus haut', 'BPM mais alto')
_tr7('history.export_col.baseline_bpm', '安静時ベースライン', '静息基线', 'Базовая линия покоя', 'Línea base en reposo', 'Ruhebasislinie', 'Ligne de base au repos', 'Linha de base em repouso')
_tr7('history.export_col.over_min', 'しきい値超え（分）', '超阈（分钟）', 'Выше порога (мин)', 'Sobre el límite (min)', 'Über der Grenze (Min)', 'Au-dessus du seuil (min)', 'Acima do limite (min)')
_tr7('history.export_col.breathing', '呼吸の発動', '呼吸触发', 'Дыхание запущено', 'Respiración lanzada', 'Atmung ausgelöst', 'Respiration déclenchée', 'Respiração disparada')
_tr7('history.export_col.peak_stress', '負荷のピーク', '负荷峰值', 'Пик нагрузки', 'Pico de carga', 'Last-Spitze', 'Pic de charge', 'Pico de carga')
_tr7('history.export_col.hrr_bpm', '回復（HRR）', '恢复（HRR）', 'Восстановление (HRR)', 'Recuperación (HRR)', 'Erholung (HRR)', 'Récupération (HRR)', 'Recuperação (HRR)')
_tr7('history.export_col.calm_min', '平静（分）', '平静（分钟）', 'Покой (мин)', 'Calma (min)', 'Ruhig (Min)', 'Calme (min)', 'Calmo (min)')
_tr7('history.export_col.raised_min', 'やや上昇（分）', '略高（分钟）', 'Повышенная (мин)', 'Elevada (min)', 'Erhöht (Min)', 'Élevée (min)', 'Elevada (min)')
_tr7('history.export_col.high_min', '高い（分）', '偏高（分钟）', 'Высокая (мин)', 'Alta (min)', 'Hoch (Min)', 'Haute (min)', 'Alta (min)')
_tr7('history.export_col.critical_min', '危険域（分）', '临界（分钟）', 'Критическая (мин)', 'Crítica (min)', 'Kritisch (Min)', 'Critique (min)', 'Crítica (min)')

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
_tr7('settings.game_lang_sub', 'アプリがゲーム中に描く文字の言語 — 心拍パネルとビジュアルの下の説明。これはストリームの視聴者にも見えるので、アプリ自体が別の言語でも既定は英語。', '应用绘制到游戏里的文字语言 — 心率面板和视觉效果下方的说明。直播观众也会看到，所以即使应用本身不是英文，默认也用英文。', 'Язык текста, который приложение рисует в игре, — панель пульса и подписи под визуалами. Это видят и зрители на стриме, поэтому по умолчанию английский, даже если само приложение на другом языке.', 'El idioma del texto que la app dibuja dentro del juego: el panel de pulso y los rótulos bajo los visuales. Tus espectadores también lo ven, por eso el inglés es el valor por defecto aunque la app no lo esté.', 'Die Sprache des Textes, den die App ins Spiel zeichnet — das Puls-Panel und die Beschriftungen unter den Visuals. Das sehen auch deine Stream-Zuschauer, deshalb ist Englisch die Vorgabe, selbst wenn die App es nicht ist.', 'La langue du texte que l’app dessine dans le jeu — le panneau de pouls et les légendes sous les visuels. Tes spectateurs le voient aussi, c’est pourquoi l’anglais est la valeur par défaut même si l’app ne l’est pas.', 'O idioma do texto que o app desenha dentro do jogo — o painel de pulso e as legendas por baixo dos visuais. Os teus espectadores também o veem, por isso o inglês é a predefinição mesmo que o app não esteja.')

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
    'session.end.none_never': _sk_en(
        'Záťaž sa ani raz nedostala nad hranicu — telo bolo celý čas v pohode.',
        'Your load never crossed the threshold — your body stayed fine the whole time.'),
    'session.end.none_short': _sk_en(
        'Záťaž hore bola, ale najdlhšie {najdlhsie} s v kuse — potrebujem {treba} s.',
        'Your load did rise, but the longest stretch was {najdlhsie} s — I need {treba} s.'),
    'session.end.none_dropouts': _sk_en(
        'Tep {n}× vypadol a počítanie sa prerušilo. Skús hodinky bližšie k počítaču.',
        'The pulse dropped out {n}× and the count restarted. Try the watch closer to the PC.'),
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
        'Všetko ostáva na tomto počítači. Nič sa nikam neposiela.',
        'Everything stays on this computer. Nothing is sent anywhere.'),
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
    'data.delete.confirm': _sk_en('Zmazať', 'Delete'),
    'data.delete.done': _sk_en('Zmazané ({n} položiek).', 'Deleted ({n} items).'),
    'data.export.btn': _sk_en('Exportovať všetko (JSON)', 'Export everything (JSON)'),
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
    'data.import.flagged': _sk_en(
        'Importované záznamy sa označia a do výpočtu účinnosti nevstúpia — cudzie telo nie je tvoje telo.',
        'Imported records are flagged and left out of the efficacy figures — someone else’s body is not yours.'),
    'data.import.merge': _sk_en('Zlúčiť s mojimi', 'Merge with mine'),
    'data.import.replace': _sk_en('Nahradiť moje', 'Replace mine'),
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
_tr7('dev.title', 'チューニング', '调参', 'Настройка', 'Ajustes finos', 'Feinabstimmung', 'Réglage', 'Afinação')
_tr7('dev.hint', '文献から来た数字で、あなたの体から来たものではない。変更できるのはセッションの合間だけ — 途中で変えると動く的を測ることになる。各測定ウィンドウはどの値で作られたか覚えている。', '这些数字来自文献，不是来自你的身体。只能在两次记录之间修改 — 中途修改就是在测一个移动的目标。每个测量窗口都记得自己是用哪些值生成的。', 'Числа из литературы, а не из твоего тела. Меняются только между сессиями — посреди сессии ты мерил бы движущуюся мишень. Каждое измерительное окно помнит, с какими значениями возникло.', 'Números de la literatura, no de tu cuerpo. Solo se cambian entre sesiones: a mitad estarías midiendo un blanco en movimiento. Cada ventana de medición recuerda con qué valores se hizo.', 'Zahlen aus der Literatur, nicht aus deinem Körper. Änderbar nur zwischen Sitzungen — mittendrin würdest du ein bewegtes Ziel messen. Jedes Messfenster merkt sich, mit welchen Werten es entstand.', 'Des chiffres tirés de la littérature, pas de ton corps. Modifiables seulement entre les séances — en cours, tu mesurerais une cible mouvante. Chaque fenêtre de mesure retient avec quelles valeurs elle a été faite.', 'Números da literatura, não do teu corpo. Só mudam entre sessões — a meio estarias a medir um alvo em movimento. Cada janela de medição lembra-se com que valores foi feita.')
_tr7('dev.locked', 'セッション中なので変更できない。心拍センサーを切ってから開き直して。', '记录进行中，无法修改。请关闭心率传感器后重新打开。', 'Сессия идёт, менять нельзя. Выключи датчик пульса и открой заново.', 'Hay una sesión en curso, no se pueden cambiar. Apaga el sensor y vuelve a abrir esto.', 'Eine Sitzung läuft, daher gesperrt. Schalte den Sensor aus und öffne das erneut.', 'Une séance est en cours, c’est verrouillé. Coupe le capteur et rouvre ceci.', 'Há uma sessão a decorrer, por isso está bloqueado. Desliga o sensor e abre isto de novo.')
_tr7('dev.param.stress_threshold', '負荷のしきい値', '负荷阈值', 'Порог нагрузки', 'Umbral de carga', 'Last-Schwelle', 'Seuil de charge', 'Limiar de carga')
_tr7('dev.param.stress_hold_s', 'しきい値を超えている時間', '超过阈值的持续时间', 'Время над порогом', 'Tiempo por encima', 'Zeit über der Schwelle', 'Temps au-dessus du seuil', 'Tempo acima do limiar')
_tr7('dev.param.dip_grace_s', '許容する落ち込み', '容许的回落', 'Допустимый провал', 'Caída tolerada', 'Tolerierter Einbruch', 'Creux toléré', 'Queda tolerada')
_tr7('dev.param.pause_s', '休みのしきい値', '停顿阈值', 'Порог паузы', 'Umbral de pausa', 'Pausen-Schwelle', 'Seuil de pause', 'Limiar de pausa')
_tr7('dev.param.max_wait_s', '最長の待ち時間', '最长等待', 'Максимум ожидания', 'Espera máxima', 'Längste Wartezeit', 'Attente maximale', 'Espera máxima')
_tr7('dev.param.away_s', '席を外した', '离开电脑', 'Отошёл от ПК', 'Se alejó del PC', 'Vom PC weg', 'Absent du PC', 'Longe do PC')
_tr7('dev.param.min_gap_s', 'ひとことの間隔', '提醒间隔', 'Промежуток между подсказками', 'Intervalo entre avisos', 'Abstand zwischen Hinweisen', 'Intervalle entre rappels', 'Intervalo entre lembretes')
_tr7('dev.silent', '黙る割合（0〜1）', '静默比例（0–1）', 'Доля тихих подсказок (0–1)', 'Proporción de avisos silenciosos (0–1)', 'Anteil stiller Hinweise (0–1)', 'Part de rappels silencieux (0–1)', 'Proporção de lembretes silenciosos (0–1)')
_tr7('dev.reset', '既定値', '默认值', 'По умолчанию', 'Por defecto', 'Standardwerte', 'Valeurs par défaut', 'Predefinições')
_tr7('dev.fire', '今すぐ出す', '立即触发', 'Выстрелить сейчас', 'Lanzar ahora', 'Jetzt auslösen', 'Déclencher maintenant', 'Disparar agora')
_tr7('dev.windows', '直近の測定ウィンドウ', '最近的测量窗口', 'Последние измерительные окна', 'Últimas ventanas de medición', 'Letzte Messfenster', 'Dernières fenêtres de mesure', 'Últimas janelas de medição')
_tr7('dev.windows_empty', 'まだない。', '还没有。', 'Пока нет.', 'Todavía ninguna.', 'Noch keine.', 'Aucune pour l’instant.', 'Ainda nenhuma.')
_tr7('dev.bad_number', 'どれかの欄が数字ではない。', '有一个字段不是数字。', 'Одно из полей не число.', 'Uno de los campos no es un número.', 'Eines der Felder ist keine Zahl.', 'L’un des champs n’est pas un nombre.', 'Um dos campos não é um número.')
_tr7('dev.applied', 'チューニング：保存した。次のセッションから有効。', '调参：已保存，从下次记录开始生效。', 'Настройка: значения сохранены, действуют со следующей сессии.', 'Ajustes: guardados, se aplican desde la próxima sesión.', 'Feinabstimmung: gespeichert, gilt ab der nächsten Sitzung.', 'Réglage : enregistré, effectif dès la prochaine séance.', 'Afinação: guardado, aplica-se a partir da próxima sessão.')
_tr7('session.end.title', '{time} プレイした。', '你玩了 {time}。', 'Ты играл {time}.', 'Jugaste {time}.', 'Du hast {time} gespielt.', 'Tu as joué {time}.', 'Jogaste {time}.')
_tr7('session.end.cues', '{n} 回声をかけた。そのうち {silent} 回はわざと黙った — 比べるものが要るから。', '我提醒了 {n} 次。其中 {silent} 次我故意没出声，这样才有得比较。', 'Я подала голос {n} раз. Из них {silent} раз намеренно промолчала — чтобы было с чем сравнить.', 'Hablé {n} veces. De esas, {silent} callé a propósito, para tener con qué comparar.', 'Ich habe {n}× gesprochen. Davon war ich {silent}× absichtlich still, damit ich etwas zum Vergleichen habe.', 'J’ai parlé {n} fois. Dont {silent} fois je me suis tue exprès, pour avoir un point de comparaison.', 'Falei {n} vezes. Dessas, {silent} fiquei em silêncio de propósito, para ter com que comparar.')
_tr7('session.end.none_never', '負荷は一度もしきい値を超えませんでした — ずっと落ち着いていました。', '负荷一次也没有越过阈值 — 你全程都很平静。', 'Нагрузка ни разу не перешла порог — тело всё время было в порядке.', 'La carga no superó el umbral ni una vez: tu cuerpo estuvo bien todo el rato.', 'Deine Belastung hat die Schwelle nie überschritten — dein Körper war die ganze Zeit ruhig.', 'Ta charge n’a jamais dépassé le seuil — ton corps est resté tranquille tout du long.', 'A tua carga nunca passou o limiar — o teu corpo esteve bem o tempo todo.')
_tr7('session.end.none_short', '負荷は上がりましたが、連続で最長 {najdlhsie} 秒 — {treba} 秒必要です。', '负荷确实升高了，但最长连续 {najdlhsie} 秒 — 我需要 {treba} 秒。', 'Нагрузка поднималась, но дольше всего {najdlhsie} с подряд — нужно {treba} с.', 'La carga sí subió, pero lo más largo fueron {najdlhsie} s seguidos: necesito {treba} s.', 'Die Belastung stieg, aber am längsten {najdlhsie} s am Stück — ich brauche {treba} s.', 'La charge est montée, mais au plus long {najdlhsie} s d’affilée — il m’en faut {treba}.', 'A carga subiu, mas no máximo {najdlhsie} s seguidos — preciso de {treba} s.')
_tr7('session.end.none_dropouts', '心拍が {n} 回途切れ、カウントがやり直しになりました。時計をPCの近くに。', '心率中断了 {n} 次，计数重新开始。把手表放得离电脑近一些。', 'Пульс пропадал {n} раз, и счёт начинался заново. Попробуй часы ближе к ПК.', 'El pulso se cortó {n} veces y la cuenta volvió a empezar. Prueba el reloj más cerca del PC.', 'Der Puls fiel {n}× aus und die Zählung begann neu. Versuch die Uhr näher am PC.', 'Le pouls a été perdu {n} fois et le compte a recommencé. Essaie la montre plus près du PC.', 'O pulso falhou {n}× e a contagem recomeçou. Tenta o relógio mais perto do PC.')
_tr7('session.end.cues_none', '今日は一度も声をかけなかった。', '今天我一次也没出声。', 'Сегодня я не подала голос ни разу.', 'Hoy no hablé ni una vez.', 'Heute habe ich kein einziges Mal gesprochen.', 'Aujourd’hui je n’ai pas parlé une seule fois.', 'Hoje não falei nem uma vez.')
_tr7('session.context.body_question', '体に入っていたものはありますか？', '你摄入了以下哪些？', 'Было ли что-то из этого в организме?', '¿Habías tomado algo de esto?', 'Hattest du etwas davon intus?', 'Avais-tu pris l’un de ces produits ?', 'Tinhas algum destes no corpo?')
_tr7('session.context.caffeine', 'カフェイン / エナジードリンク', '咖啡因 / 能量饮料', 'кофеин / энергетик', 'cafeína / bebida energética', 'Koffein / Energydrink', 'caféine / boisson énergisante', 'cafeína / bebida energética')
_tr7('session.context.alcohol', 'アルコール', '酒精', 'алкоголь', 'alcohol', 'Alkohol', 'alcool', 'álcool')
_tr7('session.context.nicotine', 'ニコチン', '尼古丁', 'никотин', 'nicotina', 'Nikotin', 'nicotine', 'nicotina')
_tr7('session.context.tired', '睡眠不足', '睡眠不足', 'мало сна', 'poco sueño', 'wenig Schlaf', 'peu de sommeil', 'pouco sono')
_tr7('session.context.question', 'こういうことはあった？', '有发生这些情况吗？', 'Что-то из этого было?', '¿Pasó algo de esto?', 'Ist etwas davon passiert?', 'Est-ce que quelque chose de tout ça est arrivé ?', 'Aconteceu alguma destas coisas?')
_tr7('session.context.why', '話すと呼吸が変わって心拍が上がる。これがないと、そういう夜は「声かけが効かない」ように見えてしまう — 実際は関係ないのに。', '说话时呼吸会变、心率会升高。没有这一项，这样的夜晚看起来就像提醒没用 — 其实毫无关系。', 'Когда говоришь, меняется дыхание и пульс растёт. Без этого такой вечер выглядел бы так, будто подсказки не работают — хотя дело вообще не в них.', 'Cuando hablas cambia tu respiración y sube el pulso. Sin esto, esa noche parecería que los avisos no sirven, cuando no tienen nada que ver.', 'Beim Sprechen ändert sich die Atmung und der Puls steigt. Ohne das sähe so ein Abend aus, als würden die Hinweise nichts bringen — obwohl es gar nicht an ihnen liegt.', 'Quand tu parles, ta respiration change et ton pouls monte. Sans ça, une telle soirée donnerait l’impression que les rappels ne servent à rien — alors qu’ils n’y sont pour rien.', 'Quando falas, a respiração muda e o pulso sobe. Sem isto, uma noite dessas pareceria que os lembretes não funcionam — quando não têm nada a ver.')
_tr7('session.context.call', '誰かと通話した', '在语音通话', 'созванивался', 'estuve en una llamada', 'war im Call', 'j’étais en vocal', 'estive numa chamada')
_tr7('session.context.laugh', '笑っていた', '一直在笑', 'смеялся', 'me estuve riendo', 'habe gelacht', 'j’ai ri', 'estive a rir')
_tr7('session.context.grind', '作業ゲー', '刷本', 'гринд', 'grindeo', 'Grind', 'grind', 'grind')
_tr7('session.context.competitive', 'ランク・競技', '排位', 'соревновательное', 'competitivo', 'kompetitiv', 'compétitif', 'competitivo')
_tr7('session.context.chill', 'まったり', '休闲', 'чилл', 'relajado', 'entspannt', 'tranquille', 'tranquilo')
_tr7('session.end.skip', 'スキップ', '跳过', 'Пропустить', 'Omitir', 'Überspringen', 'Passer', 'Ignorar')
_tr7('data.title', 'あなたのデータ', '你的数据', 'Твои данные', 'Tus datos', 'Deine Daten', 'Tes données', 'Os teus dados')
_tr7('data.hint', 'すべてこのパソコンに残る。どこにも送らない。', '全部留在这台电脑上，不会发送到任何地方。', 'Всё остаётся на этом компьютере. Никуда не отправляется.', 'Todo se queda en este ordenador. No se envía a ninguna parte.', 'Alles bleibt auf diesem Rechner. Es wird nichts versendet.', 'Tout reste sur cet ordinateur. Rien n’est envoyé nulle part.', 'Tudo fica neste computador. Nada é enviado para lado nenhum.')
_tr7('data.delete.btn', '履歴を削除', '删除历史', 'Удалить историю', 'Borrar historial', 'Verlauf löschen', 'Supprimer l’historique', 'Apagar histórico')
_tr7('data.delete.title', '履歴を削除する？', '删除历史？', 'Удалить историю?', '¿Borrar historial?', 'Verlauf löschen?', 'Supprimer l’historique ?', 'Apagar histórico?')
_tr7('data.delete.intro', 'これが消える。元には戻せない：', '以下内容将被删除，且无法恢复：', 'Будет удалено, и вернуть это нельзя:', 'Se borrará esto y no se puede deshacer:', 'Das wird gelöscht und lässt sich nicht rückgängig machen:', 'Ceci sera supprimé et ne pourra pas être récupéré :', 'Isto será apagado e não pode ser recuperado:')
_tr7('data.delete.sessions', 'セッション履歴', '记录历史', 'история сессий', 'historial de sesiones', 'Sitzungsverlauf', 'historique des séances', 'histórico de sessões')
_tr7('data.delete.windows', '測定ウィンドウ', '测量窗口', 'измерительные окна', 'ventanas de medición', 'Messfenster', 'fenêtres de mesure', 'janelas de medição')
_tr7('data.delete.insights', '分析の所見', '分析结论', 'наблюдения из анализа', 'observaciones del análisis', 'Beobachtungen aus der Analyse', 'observations de l’analyse', 'observações da análise')
_tr7('data.delete.logs', 'ログ', '日志', 'логи', 'registros', 'Logs', 'journaux', 'registos')
_tr7('data.delete.empty', '（空）', '（空）', '(пусто)', '(vacío)', '(leer)', '(vide)', '(vazio)')
_tr7('data.delete.confirm', '削除', '删除', 'Удалить', 'Borrar', 'Löschen', 'Supprimer', 'Apagar')
_tr7('data.delete.done', '削除した（{n} 件）。', '已删除（{n} 项）。', 'Удалено ({n}).', 'Borrado ({n} elementos).', 'Gelöscht ({n} Einträge).', 'Supprimé ({n} éléments).', 'Apagado ({n} itens).')
_tr7('data.export.btn', 'すべて書き出す（JSON）', '导出全部（JSON）', 'Экспортировать всё (JSON)', 'Exportar todo (JSON)', 'Alles exportieren (JSON)', 'Tout exporter (JSON)', 'Exportar tudo (JSON)')
_tr7('data.export.hint', '履歴と測定ウィンドウをまとめて一つのファイルに — 別のパソコンへ移すため。', '把全部历史和测量窗口放进一个文件 — 便于转移到另一台电脑。', 'Вся история и измерительные окна в одном файле — чтобы перенести на другой компьютер.', 'Todo el historial y las ventanas de medición en un archivo, para pasarlo a otro ordenador.', 'Der ganze Verlauf und die Messfenster in einer Datei — zum Umzug auf einen anderen Rechner.', 'Tout l’historique et les fenêtres de mesure dans un fichier — pour passer sur un autre ordinateur.', 'Todo o histórico e as janelas de medição num ficheiro — para passar para outro computador.')
_tr7('data.export.done', '保存した：{path}', '已保存：{path}', 'Сохранено: {path}', 'Guardado: {path}', 'Gespeichert: {path}', 'Enregistré : {path}', 'Guardado: {path}')
_tr7('data.import.btn', 'ファイルから読み込む', '从文件导入', 'Импортировать из файла', 'Importar desde un archivo', 'Aus Datei importieren', 'Importer depuis un fichier', 'Importar de um ficheiro')
_tr7('data.import.title', 'データを読み込む', '导入数据', 'Импорт данных', 'Importar datos', 'Daten importieren', 'Importer des données', 'Importar dados')
_tr7('data.import.found', 'ファイルにセッション {sessions} 件、測定ウィンドウ {windows} 件。', '文件中有 {sessions} 条记录和 {windows} 个测量窗口。', 'В файле {sessions} сессий и {windows} измерительных окон.', 'El archivo tiene {sessions} sesiones y {windows} ventanas de medición.', 'Die Datei enthält {sessions} Sitzungen und {windows} Messfenster.', 'Le fichier contient {sessions} séances et {windows} fenêtres de mesure.', 'O ficheiro tem {sessions} sessões e {windows} janelas de medição.')
_tr7('data.import.dropped', '{n} 件は読めず、飛ばした。', '有 {n} 条无法读取，已跳过。', '{n} записей не удалось прочитать, они пропущены.', '{n} registros no se pudieron leer y se omitieron.', '{n} Einträge konnten nicht gelesen werden und wurden übersprungen.', '{n} enregistrements illisibles ont été ignorés.', '{n} registos não puderam ser lidos e foram ignorados.')
_tr7('data.import.flagged', '読み込んだ記録には印がつき、効果の集計には入らない — 他人の体はあなたの体ではない。', '导入的记录会被标记，不计入效果统计 — 别人的身体不是你的身体。', 'Импортированные записи помечаются и не входят в подсчёт эффективности — чужое тело не твоё тело.', 'Los registros importados se marcan y no entran en el cálculo de eficacia: el cuerpo de otro no es el tuyo.', 'Importierte Einträge werden markiert und fließen nicht in die Wirksamkeit ein — ein fremder Körper ist nicht deiner.', 'Les enregistrements importés sont marqués et n’entrent pas dans le calcul d’efficacité — le corps d’un autre n’est pas le tien.', 'Os registos importados são marcados e não entram no cálculo de eficácia — o corpo de outra pessoa não é o teu.')
_tr7('data.import.merge', '自分のものと統合', '与我的合并', 'Объединить с моими', 'Combinar con los míos', 'Mit meinen zusammenführen', 'Fusionner avec les miens', 'Juntar aos meus')
_tr7('data.import.replace', '自分のものを置き換える', '替换我的', 'Заменить мои', 'Reemplazar los míos', 'Meine ersetzen', 'Remplacer les miens', 'Substituir os meus')
_tr7('data.import.done', '読み込んだ：セッション {sessions} 件、ウィンドウ {windows} 件。', '已导入：{sessions} 条记录，{windows} 个窗口。', 'Импортировано: {sessions} сессий, {windows} окон.', 'Importado: {sessions} sesiones, {windows} ventanas.', 'Importiert: {sessions} Sitzungen, {windows} Fenster.', 'Importé : {sessions} séances, {windows} fenêtres.', 'Importado: {sessions} sessões, {windows} janelas.')
_tr7('data.import.not_json', 'これは有効な JSON ファイルではない。', '这不是有效的 JSON 文件。', 'Это не корректный файл JSON.', 'Este no es un archivo JSON válido.', 'Das ist keine gültige JSON-Datei.', 'Ce n’est pas un fichier JSON valide.', 'Este não é um ficheiro JSON válido.')
_tr7('data.import.unreadable', 'ファイルを読めない。', '无法读取该文件。', 'Файл не читается.', 'No se puede leer el archivo.', 'Die Datei lässt sich nicht lesen.', 'Le fichier ne peut pas être lu.', 'O ficheiro não pode ser lido.')
_tr7('data.import.foreign', 'このファイルは Zanshin の書き出しではない。', '这个文件不是 Zanshin 的导出文件。', 'Этот файл не является экспортом из Zanshin.', 'Este archivo no es una exportación de Zanshin.', 'Diese Datei ist kein Export aus Zanshin.', 'Ce fichier n’est pas un export de Zanshin.', 'Este ficheiro não é uma exportação do Zanshin.')
_tr7('data.import.newer', 'ファイルは新しいバージョンのもの。アプリを更新して。', '文件来自更新的版本，请更新应用。', 'Файл из более новой версии приложения. Обнови приложение.', 'El archivo es de una versión más nueva. Actualiza la app.', 'Die Datei stammt aus einer neueren Version. Aktualisiere die App.', 'Le fichier vient d’une version plus récente. Mets l’app à jour.', 'O ficheiro é de uma versão mais recente. Atualiza a app.')
_tr7('data.import.empty', 'ファイルに使える記録がない。', '文件中没有可用的记录。', 'В файле нет пригодных записей.', 'El archivo no contiene registros utilizables.', 'Die Datei enthält keine brauchbaren Einträge.', 'Le fichier ne contient aucun enregistrement utilisable.', 'O ficheiro não contém registos utilizáveis.')
_tr7('efficacy.empty', 'まだ何もありません。これは待つのではなく、プレイすることで貯まります。', '还没有数据。这是靠玩累积的，不是靠等。', 'Пока ничего. Это накапливается игрой, а не ожиданием.', 'Todavía nada. Esto se acumula jugando, no esperando.', 'Noch nichts. Das sammelt sich beim Spielen an, nicht beim Warten.', 'Rien pour l’instant. Cela s’accumule en jouant, pas en attendant.', 'Ainda nada. Isto acumula-se a jogar, não a esperar.')
_tr7('log.cue_delivered', '身体へのひとこと：{label}', '身体提醒：{label}', 'Телесное напоминание: {label}', 'Recordatorio corporal: {label}', 'Körper-Hinweis: {label}', 'Rappel corporel : {label}', 'Lembrete corporal: {label}')
_tr7('log.game_lang', 'ゲーム中の言語：{lang}', '游戏中的语言：{lang}', 'Язык в игре: {lang}', 'Idioma en el juego: {lang}', 'Sprache im Spiel: {lang}', 'Langue en jeu : {lang}', 'Idioma no jogo: {lang}')


# --------------------------------------------------------------------------
# Doplnene preklady (final i18n) - realne chybajuce retazce do 7 jazykov.
# Patchuje existujuce zaznamy v STRINGS (nemeni sk/en).
# --------------------------------------------------------------------------
_DOPLNENE_PREKLADY = {
    "kamae.no_hr": {"ja": "心拍を待っています", "zh": "正在等待心率", "ru": "Ожидаю пульс", "es": "Esperando las pulsaciones", "de": "Warte auf den Puls", "fr": "En attente du rythme cardiaque", "pt": "À espera do ritmo cardíaco"},
    "kamae.no_hr_sub": {"ja": "センサーは待ち受けていますが、時計からはまだ何も届いていません。ちゃんと計測しているか、そして同じWi‑Fiにつながっているか確認してください。", "zh": "传感器正在监听，但手表那边还没有传来任何数据。请检查它是否真的在测量，并且连的是同一个 Wi‑Fi。", "ru": "Датчик слушает, но с часов пока ничего не приходит. Проверь, что они действительно измеряют и находятся в той же сети Wi‑Fi.", "es": "El sensor está escuchando, pero del reloj todavía no llega nada. Comprueba que de verdad esté midiendo y en la misma Wi‑Fi.", "de": "Der Sensor hört zu, aber von der Uhr kommt noch nichts. Prüf, ob sie wirklich misst und im selben WLAN ist.", "fr": "Le capteur écoute, mais rien n'arrive encore de la montre. Vérifie qu'elle mesure vraiment et qu'elle est sur le même Wi‑Fi.", "pt": "O sensor está à escuta, mas ainda não chega nada do relógio. Verifica se está mesmo a medir e se está na mesma Wi‑Fi."},
    "settings.hr_status_no_client": {"ja": "待ち受け中ですが、まだ誰もつながっていません", "zh": "正在监听，但还没有设备连接", "ru": "Слушаю, но никто не подключился", "es": "Escuchando, pero no se ha conectado nadie", "de": "Höre zu, aber niemand hat sich verbunden", "fr": "À l'écoute, mais personne ne s'est connecté", "pt": "À escuta, mas ninguém se ligou"},
    "settings.hr_status_busy_gave_up": {"ja": "ポートが使用中です — センサーをオフにしました", "zh": "端口被占用 — 传感器已关闭", "ru": "Порт занят — датчик выключен", "es": "El puerto está ocupado — sensor apagado", "de": "Port ist belegt — Sensor ausgeschaltet", "fr": "Le port est occupé — capteur désactivé", "pt": "A porta está ocupada — sensor desligado"},
    "guide.panel_subtitle": {"ja": "それぞれの合図のときに体の中で何が起きているか、そしてアプリが声をかけてきたら何をすればいいか。", "zh": "每条提示出现时你的身体会发生什么，以及当应用出声提醒时你该怎么做。", "ru": "Что происходит в твоём теле при каждой подсказке и что с этим делать, когда приложение подаёт голос.", "es": "Qué pasa en tu cuerpo con cada aviso y qué hacer cuando la app te habla.", "de": "Was in deinem Körper bei jedem Hinweis passiert und was du damit machen kannst, wenn die App sich meldet.", "fr": "Ce qui se passe dans ton corps à chaque signal, et quoi faire quand l'appli te parle.", "pt": "O que se passa no teu corpo a cada aviso e o que fazer quando a aplicação se manifesta."},
    "about.title": {"ja": "このアプリについて", "zh": "关于", "ru": "О приложении", "es": "Acerca de", "de": "Über die App", "fr": "À propos", "pt": "Sobre"},
    "about.lead": {"ja": "みなさん、こんにちは。Dandurfinです。", "zh": "大家好，我是 Dandurfin。", "ru": "Всем привет, это Dandurfin.", "es": "Hola a todos, aquí Dandurfin.", "de": "Hallo zusammen, hier ist Dandurfin.", "fr": "Salut à tous, ici Dandurfin.", "pt": "Olá a todos, aqui o Dandurfin."},
    "about.body": {"ja": "そもそもZanshinはなぜ生まれたのか。一日の大半をパソコンの前で過ごし、配信をしたりゲームをしたりしている僕は、時間が経つうちにあるパターンに気づきました。ゲームをしていると、僕たちはよく完全な「オートパイロット」状態にすべり込んでしまいます。夢中になりすぎて時間も自分の体のことも見失ってしまうか、逆に、うまくいかないと無駄にティルトして苛立ってしまうか、どちらかなんです。\n\n僕は、激しいアクションの最中でも、ピリピリしたランクマッチの中でも、冷静な頭を保って「フロー」の状態でいられる方法を探していました。そんなときに出会ったのが、残心（ざんしん）という考え方です。武道では、完全に集中しながらもリラックスし、何にでも対応できる澄んだ心の状態を指す言葉です。\n\nこのアプリは、ただの個人的な必要から書きました。燃え尽きないように支えてくれて、ときどき深呼吸をするよう思い出させてくれて、地に足をつけさせてくれる——そんな、そっと背後で働いてくれる相棒がほしかったんです。複雑で難解な修行の話ではありません。ただ、ゲームをもっと楽しんで、もっとうまくプレイして、そして何より、何でもないことでティルトしない。それだけのことです。\n\nそして正直に言うと、僕はプログラマーでもアーティストでもありません。このアプリは「バイブコーディング」で書きました——つまりAIと一緒に、一文ずつ、走りながら覚えていったんです。僕が持ち込んだのは、アイデアと、パソコンの前で過ごした長い年月だけです。\n\n僕は巨人の肩の上に立っています。このアプリがやっていることで、僕が考え出したものは何ひとつありません——呼吸も、集中も、ゆるめた顎も、心拍とストレスの研究も、これを書くのに使った道具も。すべて誰かが僕より先に作り、そして誰でも使えるように開いたまま残しておいてくれたものです。だからこそZanshinは、GPLv3ライセンスのもとで無料かつオープンです。誰でもコードを読み、書き換え、次へ渡すことができます——ただ、閉じてしまうことだけはできません。次へ渡す人は、ソースコードと同じライセンスも一緒に手渡さなければなりません。僕はこうして受け継ぎ、こうして同じように渡していきたいのです。\n\nこの考え方にピンとくる人も、ただゲームをして一緒にゆるく過ごしたいだけの人も、ぜひ僕たちのコミュニティに立ち寄ってください：", "zh": "Zanshin 到底是怎么诞生的？作为一个每天有很大一部分时间都泡在电脑前、直播和打游戏的人，我慢慢发现了一个规律。玩游戏时，我们常常会完全进入“自动驾驶”模式。要么是太投入，以至于彻底忘了时间，也忘了自己的身体；要么反过来，一不顺就上头，为不该生气的事情生气。\n\n我一直在找一种方法，让自己即便身处激烈的战斗或紧张的排位赛中，也能保持冷静的头脑，留在“心流”里。也正是在那时，我接触到了 zanshin 这个概念——在武术里，它指的是一种全神贯注、放松、头脑清明、随时准备应对一切的状态。\n\n写这个应用，纯粹是出于我自己一个很简单的需求。我想要一个不起眼、在后台默默帮忙的小助手，让我不至于把自己耗空，时不时提醒我深呼吸一下，把我拉回地面。这里没有什么复杂玄乎的练习，说到底就是为了让我们玩游戏更开心、发挥得更好，最重要的是——别为了鸡毛蒜皮的事上头。\n\n再说得直白点：我既不是程序员，也不是美术。这个应用是我用 vibe coding 的方式写出来的——和 AI 一起，一行一行地敲，边做边学。我带进来的，就是这个点子，还有多年泡在电脑前的经历。\n\n我是站在巨人的肩膀上。这个应用所做的一切，没有一样是我发明的——呼吸、专注、放松的下颌、关于心率和压力的研究，还有写它所用的那些工具。这一切都是别人在我之前做好、并且免费公开出来的。正因如此，Zanshin 在 GPLv3 许可证下免费且开放：任何人都可以阅读代码、修改它、把它传下去——唯独不能把它封闭起来。谁把它传下去，就必须连同源代码和同一份许可证一起交出去。我是这样继承来的，也想这样传下去。\n\n如果你认同这样的心态，或者只是想一起打打游戏、聊聊天，一定要来我们的社区坐坐：", "ru": "Почему вообще появился Zanshin? Как человек, который проводит за компьютером огромную часть дня — стримлю и играю, — я со временем заметил закономерность. Играя, мы часто скатываемся в полный «автопилот». Либо увлекаемся так, что теряем счёт времени и забываем о собственном теле, либо, наоборот, ловим ненужный тильт и злимся, когда что-то не выходит.\n\nЯ искал способ сохранять холодную голову и оставаться в «потоке» даже посреди жаркого экшена или в потных ранкед-матчах. Тогда я и наткнулся на понятие zanshin — в боевых искусствах оно означает состояние полной сосредоточенности, расслабленности и ясной головы, готовой ко всему.\n\nЭто приложение я написал из простой личной потребности. Мне хотелось незаметного помощника на фоне, который не даст мне выгореть, время от времени напомнит глубоко вдохнуть и удержит меня на земле. Речь не о каких-то сложных эзотерических упражнениях — просто о том, чтобы игры приносили больше удовольствия, чтобы играть лучше и, главное, чтобы не злиться из-за ерунды.\n\nИ честно: я не программист и не художник. Это приложение я написал вайб-кодингом — то есть вместе с ИИ, строчка за строчкой, учась по ходу дела. То, что привнёс я, — это идея и годы, проведённые за компьютером.\n\nЯ стою на плечах гигантов. Ничего из того, что делает это приложение, я не придумал — дыхание, сосредоточенность, расслабленная челюсть, исследования о пульсе и стрессе, да и инструменты, на которых всё это написано. Всё это кто-то сделал до меня и оставил в свободном доступе. Поэтому Zanshin бесплатный и открытый под лицензией GPLv3: любой может посмотреть код, изменить его и передать дальше — только закрыть его нельзя. Кто передаёт его дальше, должен отдать вместе с ним и исходный код, и ту же самую лицензию. Я получил это так и хочу так же передать дальше.\n\nЕсли тебе близок этот настрой или ты просто хочешь поиграть и потусить, обязательно загляни к нам:", "es": "¿Por qué surgió Zanshin en realidad? Como alguien que pasa gran parte del día delante del PC —haciendo streaming y jugando— con el tiempo me di cuenta de un patrón. Al jugar caemos a menudo en el «piloto automático» total. O nos metemos tanto que perdemos la noción del tiempo y de nuestro propio cuerpo, o al revés, pillamos un tilt innecesario y nos frustramos cuando las cosas no salen.\n\nBuscaba una forma de mantener la cabeza fría y quedarme en el «flow» incluso en plena acción o en partidas sweaty de ranked. Fue entonces cuando di con el concepto de zanshin — que en las artes marciales designa un estado de concentración plena, relajación y mente clara, lista para cualquier cosa.\n\nProgramé esta app por una simple necesidad personal. Quería un ayudante discreto en segundo plano que no me deje quemarme, que de vez en cuando me recuerde respirar hondo y que me mantenga con los pies en la tierra. No se trata de ningún ejercicio esotérico complicado; se trata simplemente de disfrutar más de los juegos, jugar mejor y, sobre todo, no cabrearnos por nada.\n\nY os lo digo sin rodeos: no soy programador ni artista. Esta app la hice a base de vibe coding — junto con la IA, línea a línea, aprendiendo sobre la marcha. Lo que puse yo es la idea y los años pasados delante del PC.\n\nEstoy a hombros de gigantes. Nada de lo que hace esta app lo inventé yo — la respiración, la concentración, la mandíbula relajada, la investigación sobre el ritmo cardíaco y el estrés, las herramientas con las que está escrita. Todo eso ya lo hizo alguien antes que yo y lo dejó a disposición de todos. Por eso Zanshin es gratuito y abierto bajo la licencia GPLv3: cualquiera puede leer el código, modificarlo y pasarlo adelante — lo único que no puede es cerrarlo. Quien lo pase adelante tiene que entregar también el código fuente y la misma licencia. Yo lo heredé así y quiero entregarlo de la misma manera.\n\nSi esta forma de ver las cosas te encaja, o si solo quieres echar unas partidas y pasar el rato, pásate sin falta por nuestra comunidad:", "de": "Warum ist Zanshin eigentlich entstanden? Als jemand, der einen großen Teil des Tages am PC verbringt — ich streame und zocke — ist mir mit der Zeit ein Muster aufgefallen. Beim Spielen rutschen wir oft in den kompletten „Autopilot“. Entweder vertiefen wir uns so sehr, dass wir das Zeitgefühl und den eigenen Körper völlig verlieren, oder wir fangen uns umgekehrt unnötigen Tilt ein und ärgern uns, wenn es nicht läuft.\n\nIch habe nach einem Weg gesucht, einen kühlen Kopf zu bewahren und selbst mitten in der Action oder in sweaty Ranked-Matches im „Flow“ zu bleiben. Damals bin ich auf den Begriff Zanshin gestoßen — in den Kampfkünsten bezeichnet er einen Zustand voller Konzentration, Entspannung und eines klaren Kopfes, der auf alles vorbereitet ist.\n\nDiese App habe ich aus einem ganz einfachen persönlichen Bedürfnis geschrieben. Ich wollte einen unaufdringlichen Helfer im Hintergrund, der mich nicht ausbrennen lässt, mich ab und zu ans tiefe Durchatmen erinnert und mich auf dem Boden hält. Es geht um keine komplizierten esoterischen Übungen — es geht einfach darum, dass uns die Spiele mehr Spaß machen, dass wir besser spielen und vor allem, dass wir uns nicht wegen Kleinigkeiten aufregen.\n\nUnd ganz ehrlich: Ich bin weder Programmierer noch Grafiker. Diese App habe ich per Vibe Coding geschrieben — also zusammen mit KI, Satz für Satz, und ich habe im Laufen dazugelernt. Was ich beigetragen habe, ist die Idee und die Jahre, die ich am PC verbracht habe.\n\nIch stehe auf den Schultern von Riesen. Nichts von dem, was die App tut, habe ich erfunden — das Atmen, die Konzentration, der gelöste Kiefer, die Forschung zu Puls und Stress und auch die Werkzeuge, in denen das Ganze geschrieben ist. Das alles hat jemand vor mir gemacht und frei zugänglich gelassen. Deshalb ist Zanshin kostenlos und offen unter der GPLv3-Lizenz: Jeder kann sich den Code ansehen, ihn ändern und weitergeben — nur zumachen darf er ihn nicht. Wer ihn weitergibt, muss den Quellcode und dieselbe Lizenz mitliefern. Ich habe es so geerbt und ich will es genauso weitergeben.\n\nWenn dir diese Einstellung zusagt, oder wenn du einfach zocken und quatschen willst, schau unbedingt bei uns vorbei:", "fr": "Pourquoi Zanshin a-t-il vu le jour, au juste ? En tant que personne qui passe une grande partie de sa journée devant le PC — à streamer et à jouer — j'ai fini par remarquer un schéma qui revient. En jouant, on bascule souvent en mode « pilote automatique » total. Soit on est tellement absorbé qu'on perd complètement la notion du temps et de son propre corps, soit, à l'inverse, on attrape un tilt inutile et on s'agace dès que ça ne va pas.\n\nJe cherchais un moyen de garder la tête froide et de rester dans le « flow » même en pleine action ou dans des parties classées bien sweaty. C'est là que je suis tombé sur le concept de zanshin — qui, dans les arts martiaux, désigne un état de concentration totale, de détente et d'esprit clair, prêt à tout.\n\nJ'ai codé cette appli par simple besoin personnel. Je voulais un assistant discret, en arrière-plan, qui m'empêche de m'épuiser, qui me rappelle de respirer profondément de temps en temps et qui me garde les pieds sur terre. Rien à voir avec des exercices ésotériques compliqués — il s'agit simplement de prendre plus de plaisir à jouer, de mieux jouer et, surtout, de ne pas s'énerver pour un rien.\n\nEt soyons clairs : je ne suis ni programmeur ni graphiste. J'ai codé cette appli en vibe coding — avec l'IA, ligne par ligne, en apprenant au fur et à mesure. Ce que j'y ai apporté, moi, c'est l'idée et les années passées devant le PC.\n\nJe me tiens sur les épaules de géants. Rien de ce que fait cette appli n'a été inventé par moi — la respiration, la concentration, la mâchoire détendue, les recherches sur le rythme cardiaque et le stress, les outils dans lesquels elle est écrite. Quelqu'un a fait tout ça avant moi et l'a laissé en libre accès. C'est pour ça que Zanshin est gratuit et ouvert sous la licence GPLv3 : n'importe qui peut lire le code, le modifier et le transmettre — il ne peut simplement pas le refermer. Celui qui le transmet doit remettre avec lui le code source et cette même licence. J'en ai hérité ainsi, et je veux le transmettre de la même façon.\n\nSi cet état d'esprit te parle, ou si tu veux juste jouer et passer un bon moment, passe faire un tour dans notre communauté :", "pt": "Porque é que o Zanshin surgiu, afinal? Como alguém que passa uma boa parte do dia ao PC — a fazer streaming e a jogar — reparei, com o tempo, num padrão. A jogar, muitas vezes entramos em pleno modo «piloto automático». Ou ficamos tão absorvidos que perdemos por completo a noção do tempo e do nosso próprio corpo, ou, pelo contrário, apanhamos um tilt desnecessário e ficamos frustrados quando as coisas correm mal.\n\nAndava à procura de uma forma de manter a cabeça fria e ficar no «flow» mesmo no meio da ação intensa ou de partidas sweaty de ranked. Foi então que dei com o conceito de zanshin — que, nas artes marciais, designa um estado de concentração total, descontração e mente limpa, pronta para tudo.\n\nEscrevi esta aplicação por uma simples necessidade pessoal. Queria um ajudante discreto em segundo plano que não me deixasse esgotar, que de vez em quando me lembrasse de respirar fundo e que me mantivesse com os pés assentes na terra. Não são exercícios esotéricos complicados — trata-se simplesmente de nos divertirmos mais com os jogos, de jogarmos melhor e, acima de tudo, de não ficarmos em tilt por nada.\n\nE agora sem rodeios: não sou programador nem artista. Fiz esta aplicação com vibe coding — ou seja, em conjunto com a IA, linha a linha, aprendendo pelo caminho. O que eu trouxe foi a ideia e os anos passados ao PC.\n\nEstou apoiado nos ombros de gigantes. Nada do que esta aplicação faz foi inventado por mim — a respiração, a concentração, o maxilar descontraído, a investigação sobre o ritmo cardíaco e o stress, e as ferramentas em que está escrita. Alguém fez tudo isto antes de mim e deixou-o livremente disponível. É por isso que o Zanshin é gratuito e aberto sob a licença GPLv3: qualquer pessoa pode ver o código, alterá-lo e passá-lo adiante — só não o pode fechar. Quem o passa adiante tem de entregar com ele também o código-fonte e a mesma licença. Herdei-o assim e assim o quero passar adiante.\n\nSe esta atitude te diz alguma coisa, ou se só queres jogar um pouco e conviver, passa de certeza pela nossa comunidade:"},
    "about.copyright": {"ja": "© 2026 Dandurfin · GNU GPLv3 · Zanshin {version}\nこのプログラムは自由なソフトウェアであり、ソースコードも一緒に付いてきます。誰でも——同じライセンスのもとで——使い、学び、改変し、共有できます。無保証です。", "zh": "© 2026 Dandurfin · GNU GPLv3 · Zanshin {version}\n本程序是自由软件，它的源代码始终随之一同传递。任何人都可以使用、研究、修改和分享它——在同一份许可证下。不提供任何担保。", "ru": "© 2026 Dandurfin · GNU GPLv3 · Zanshin {version}\nЭта программа — свободное ПО, и её исходный код идёт вместе с ней. Использовать, изучать, изменять и распространять её может кто угодно — под той же лицензией. Без каких-либо гарантий.", "es": "© 2026 Dandurfin · GNU GPLv3 · Zanshin {version}\nEste programa es software libre y su código fuente viaja con él. Cualquiera puede usarlo, estudiarlo, modificarlo y compartirlo — bajo la misma licencia. Sin ninguna garantía.", "de": "© 2026 Dandurfin · GNU GPLv3 · Zanshin {version}\nDieses Programm ist freie Software und sein Quellcode reist mit ihm. Jeder darf es nutzen, studieren, verändern und weitergeben — unter derselben Lizenz. Ohne jede Gewähr.", "fr": "© 2026 Dandurfin · GNU GPLv3 · Zanshin {version}\nCe programme est un logiciel libre et son code source voyage avec lui. Chacun peut l'utiliser, l'étudier, le modifier et le partager — sous la même licence. Sans aucune garantie.", "pt": "© 2026 Dandurfin · GNU GPLv3 · Zanshin {version}\nEste programa é software livre e o seu código-fonte viaja com ele. Qualquer pessoa o pode usar, estudar, modificar e partilhar — sob a mesma licença. Sem qualquer garantia."},
    "about.links": {"ja": "僕はここにいます", "zh": "在这里找到我", "ru": "Найдёшь меня здесь", "es": "Me encuentras aquí", "de": "Hier findest du mich", "fr": "Retrouve-moi ici", "pt": "Encontra-me aqui"},
    "about.between_lines": {"ja": "行間を読む人へ：\n\nこのアプリはストレスを測らない。測るのは、すきま——心拍が告げるものと、あなたが実際に感じるものとの間の。数字は表面、あなたは深み。\n\nそのすきまを自分の中で聞けるようになれば、ほかの場所でも聞こえてくる——人が書くことと思っていること、求めることと必要としていることの間に。\n\n何も失われない。ただ姿を変えるだけ——注意もまた。手のひらは開いたままで。", "zh": "给读得懂字里行间的人：\n\n这个应用不测量压力。它测量的是那道缝隙——你的心率所说的，与你真正所感受的之间。数字是表面；你是深处。\n\n当你学会在自己心里听见那道缝隙，你也会开始在别处听见它——在人们所写的与所想的、所求的与所需的之间。\n\n没有什么会失去。只是转化——注意力也是。把手掌摊开。", "ru": "Для того, кто читает между строк:\n\nЭто приложение не измеряет стресс. Оно измеряет зазор — между тем, что говорит твой пульс, и тем, что ты на самом деле чувствуешь. Число — это поверхность; ты — глубина.\n\nИ когда ты научишься слышать этот зазор в себе, ты начнёшь слышать его и в другом — в том, что люди пишут и что думают, чего просят и что им нужно.\n\nНичто не теряется. Оно лишь преображается — и внимание тоже. Держи ладонь открытой.", "es": "Para quien lee entre líneas:\n\nEsta app no mide el estrés. Mide la brecha — entre lo que dice tu pulso y lo que de verdad sientes. El número es la superficie; tú eres la profundidad.\n\nY cuando aprendas a oír esa brecha en ti, empezarás a oírla también en otras partes — en lo que la gente escribe y lo que piensa, en lo que pide y lo que necesita.\n\nNada se pierde. Solo se transforma — también la atención. Mantén la palma abierta.", "de": "Für den, der zwischen den Zeilen liest:\n\nDiese App misst nicht den Stress. Sie misst die Lücke — zwischen dem, was dein Puls sagt, und dem, was du wirklich fühlst. Die Zahl ist die Oberfläche; du bist die Tiefe.\n\nUnd wenn du lernst, diese Lücke in dir zu hören, wirst du sie auch anderswo hören — in dem, was Menschen schreiben und was sie meinen, worum sie bitten und was sie brauchen.\n\nNichts geht verloren. Es wandelt sich nur — auch die Aufmerksamkeit. Halte die Handfläche offen.", "fr": "Pour celui qui lit entre les lignes :\n\nCette appli ne mesure pas le stress. Elle mesure l'écart — entre ce que dit ton pouls et ce que tu ressens vraiment. Le chiffre est la surface ; toi, tu es la profondeur.\n\nEt quand tu apprendras à entendre cet écart en toi, tu commenceras à l'entendre ailleurs aussi — dans ce que les gens écrivent et ce qu'ils pensent, ce qu'ils demandent et ce dont ils ont besoin.\n\nRien ne se perd. Cela se transforme seulement — l'attention aussi. Garde la paume ouverte.", "pt": "Para quem lê nas entrelinhas:\n\nEsta aplicação não mede o stress. Mede a fenda — entre o que o teu ritmo cardíaco diz e o que realmente sentes. O número é a superfície; tu és a profundidade.\n\nE quando aprenderes a ouvir essa fenda em ti, começarás a ouvi-la também noutro lado — no que as pessoas escrevem e no que pensam, no que pedem e no que precisam.\n\nNada se perde. Apenas se transforma — a atenção também. Mantém a palma aberta."},
    "kamae.stopped_sub_auto": {"ja": "今は何も見ていません。左のボタンで起こしてください。ゲームが立ち上がれば、僕は自分から動き出します。", "zh": "什么都没在监测。用左边的按钮启动我，或者游戏一开，我就会自己启动。", "ru": "Ничего не отслеживаю. Запусти меня кнопкой слева — или я запущусь сам при старте игры.", "es": "No estoy vigilando nada. Ponme en marcha con el botón de la izquierda, o me pongo en marcha yo solo cuando arranca un juego.", "de": "Ich beobachte gerade nichts. Starte mich mit dem Knopf links, oder ich starte von selbst, sobald ein Spiel losgeht.", "fr": "Je ne surveille rien. Lance-moi avec le bouton à gauche, ou je démarre tout seul au lancement d'un jeu.", "pt": "Não estou a acompanhar nada. Inicia-me com o botão à esquerda, ou inicio-me sozinho quando um jogo arranca."},
    "log.cue_visual_failed": {"ja": "ゲーム内のビジュアルが表示されませんでした——この合図は計測から除外されます。", "zh": "游戏内的视觉提示没有渲染出来——这条提示不计入测量。", "ru": "Внутриигровой визуал не отрисовался — эта подсказка не учитывается в измерении.", "es": "El visual dentro del juego no se mostró — este aviso no se cuenta en la medición.", "de": "Das In-Game-Bild wurde nicht angezeigt — dieser Hinweis zählt nicht in die Messung.", "fr": "Le visuel en jeu ne s'est pas affiché — ce signal est exclu de la mesure.", "pt": "O visual no jogo não foi apresentado — este aviso fica excluído da medição."},
    "session.context.save_failed": {"ja": "このセッションのコンテキストを保存できませんでした——回答は保存されませんでした。", "zh": "无法保存这次会话的情境——你的回答没有被保存下来。", "ru": "Не удалось сохранить контекст этой сессии — твой ответ не сохранён.", "es": "No se pudo guardar el contexto de esta sesión — tu respuesta no se ha guardado.", "de": "Der Kontext für diese Sitzung konnte nicht gespeichert werden — deine Antwort wurde nicht behalten.", "fr": "Impossible d'enregistrer le contexte de cette session — ta réponse n'a pas été conservée.", "pt": "Não foi possível guardar o contexto desta sessão — a tua resposta não ficou guardada."},
    "data.delete.events": {"ja": "合図の記録", "zh": "提示记录", "ru": "записи подсказок", "es": "registros de avisos", "de": "Aufgezeichnete Hinweise", "fr": "enregistrements des signaux", "pt": "registos de avisos"},
    "data.delete.tts": {"ja": "読み上げた合図（キャッシュ）", "zh": "语音提示（缓存）", "ru": "озвученные подсказки (кэш)", "es": "avisos hablados (caché)", "de": "Gesprochene Hinweise (Cache)", "fr": "signaux vocaux (cache)", "pt": "avisos falados (cache)"},
    "data.delete.backup": {"ja": "バックアップ", "zh": "备份", "ru": "резервная копия", "es": "copia de seguridad", "de": "Sicherung", "fr": "sauvegarde", "pt": "cópia de segurança"},
    "history.col_minmax": {"ja": "最小 / 最大", "zh": "最小 / 最大", "ru": "Мин / макс", "es": "Min / max", "de": "Min / max", "fr": "Min / max", "pt": "Mín / máx"},
    "onboarding.modern.title": {"ja": "藍 Aizome — 藍色", "zh": "藍 Aizome — 靛蓝", "ru": "藍 Aizome — индиго", "es": "藍 Aizome — índigo", "de": "藍 Aizome — Indigo", "fr": "藍 Aizome — indigo", "pt": "藍 Aizome — índigo"},
    # --- Kontext relacie: cinnost (hral/pracoval) + vlastna poznamka ---
    "session.context.activity_question": {"sk": "Hral si, alebo pracoval?", "en": "Were you playing or working?", "ja": "遊んでいた？それとも作業していた？", "zh": "你是在玩，还是在工作？", "ru": "Ты играл или работал?", "es": "¿Estabas jugando o trabajando?", "de": "Hast du gespielt oder gearbeitet?", "fr": "Tu jouais ou tu travaillais ?", "pt": "Estavas a jogar ou a trabalhar?"},
    "session.context.activity.play": {"sk": "Hral som", "en": "Playing", "ja": "ゲーム", "zh": "在玩", "ru": "Играл", "es": "Jugando", "de": "Gespielt", "fr": "Je jouais", "pt": "A jogar"},
    "session.context.activity.work": {"sk": "Pracoval som", "en": "Working", "ja": "作業", "zh": "在工作", "ru": "Работал", "es": "Trabajando", "de": "Gearbeitet", "fr": "Je travaillais", "pt": "A trabalhar"},
    "session.context.note_label": {"sk": "Vlastná poznámka (nepovinné)", "en": "Your own note (optional)", "ja": "自由メモ（任意）", "zh": "自己的备注（可选）", "ru": "Своя заметка (необязательно)", "es": "Nota propia (opcional)", "de": "Eigene Notiz (optional)", "fr": "Note perso (facultatif)", "pt": "Nota tua (opcional)"},
    "hud.quick_label": {"sk": "Tep v hre", "en": "In-game HR", "ja": "ゲーム内の心拍", "zh": "游戏内心率", "ru": "Пульс в игре", "es": "Pulso en juego", "de": "Puls im Spiel", "fr": "FC en jeu", "pt": "Pulso no jogo"},
    "history.export_col.activity": {"sk": "činnosť", "en": "activity", "ja": "活動", "zh": "活动", "ru": "активность", "es": "actividad", "de": "Aktivität", "fr": "activité", "pt": "atividade"},
    "history.export_col.hud_seen": {"sk": "HUD videný %", "en": "HUD seen %", "ja": "HUD表示率", "zh": "HUD可见%", "ru": "HUD виден %", "es": "HUD visto %", "de": "HUD sichtbar %", "fr": "HUD vu %", "pt": "HUD visto %"},
    "history.export_col.note": {"sk": "poznámka", "en": "note", "ja": "メモ", "zh": "备注", "ru": "заметка", "es": "nota", "de": "Notiz", "fr": "note", "pt": "nota"},
    # --- 1. kolo premenných: choroba/šport-pred, spánok, subjektívna vrstva ---
    "session.context.illness": {"sk": "cítim sa chorý / nanič", "en": "feeling ill / off", "ja": "体調が悪い", "zh": "感觉不舒服/生病", "ru": "нездоровится / болею", "es": "me siento mal / enfermo", "de": "fühle mich krank / mies", "fr": "je me sens malade / patraque", "pt": "sinto-me doente / mal"},
    "session.context.exercise_before": {"sk": "pred hraním som sa hýbal/zadýchal", "en": "moved/exerted before playing", "ja": "プレイ前に動いた/息が上がった", "zh": "玩之前运动/喘过气", "ru": "перед игрой двигался/запыхался", "es": "me moví/agité antes de jugar", "de": "vor dem Spielen bewegt/außer Atem", "fr": "bougé/essoufflé avant de jouer", "pt": "mexi-me/ofeguei antes de jogar"},
    "session.sleep.q": {"sk": "Spánok minulú noc", "en": "Sleep last night", "ja": "昨夜の睡眠", "zh": "昨晚的睡眠", "ru": "Сон прошлой ночью", "es": "Sueño anoche", "de": "Schlaf letzte Nacht", "fr": "Sommeil la nuit dernière", "pt": "Sono na noite passada"},
    "session.sleep.rested": {"sk": "vyspatý", "en": "rested", "ja": "よく寝た", "zh": "睡得好", "ru": "выспался", "es": "descansado", "de": "ausgeschlafen", "fr": "reposé", "pt": "descansado"},
    "session.sleep.mid": {"sk": "stredne", "en": "so-so", "ja": "まあまあ", "zh": "一般", "ru": "средне", "es": "regular", "de": "mittel", "fr": "moyen", "pt": "mais ou menos"},
    "session.sleep.broken": {"sk": "rozbitý", "en": "broken", "ja": "ボロボロ", "zh": "很差", "ru": "разбитый", "es": "fatal", "de": "mies", "fr": "haché", "pt": "péssimo"},
    "session.felt.header": {"sk": "Ako sa to cítilo", "en": "How it felt", "ja": "どう感じた", "zh": "感觉如何", "ru": "Как это ощущалось", "es": "Cómo se sintió", "de": "Wie es sich anfühlte", "fr": "Ressenti", "pt": "Como te sentiste"},
    "session.felt.load": {"sk": "Vnímaná záťaž", "en": "Perceived load", "ja": "感じた負荷", "zh": "主观强度", "ru": "Ощущаемая нагрузка", "es": "Carga percibida", "de": "Empfundene Last", "fr": "Charge ressentie", "pt": "Carga percebida"},
    "session.felt.load_hint": {"sk": "0 = úplný pokoj, 10 = maximálne vypätie", "en": "0 = totally calm, 10 = maxed out", "ja": "0＝完全に穏やか、10＝極限", "zh": "0＝完全平静，10＝极度紧绷", "ru": "0 = полный покой, 10 = на пределе", "es": "0 = calma total, 10 = al límite", "de": "0 = ganz ruhig, 10 = am Limit", "fr": "0 = tout calme, 10 = à fond", "pt": "0 = calma total, 10 = no limite"},
    "session.felt.valence": {"sk": "Bolo ti skôr dobre, či zle?", "en": "Did it feel good or bad?", "ja": "気分は良かった？悪かった？", "zh": "感觉是好还是坏？", "ru": "Было приятно или неприятно?", "es": "¿Te sentiste bien o mal?", "de": "Eher gut oder schlecht?", "fr": "Plutôt bien ou mal ?", "pt": "Foi antes bom ou mau?"},
    "session.felt.valence.-2": {"sk": "zle", "en": "bad", "ja": "悪い", "zh": "差", "ru": "плохо", "es": "mal", "de": "schlecht", "fr": "mal", "pt": "mau"},
    "session.felt.valence.-1": {"sk": "skôr zle", "en": "rather bad", "ja": "やや悪い", "zh": "偏差", "ru": "скорее плохо", "es": "algo mal", "de": "eher schlecht", "fr": "plutôt mal", "pt": "algo mau"},
    "session.felt.valence.0": {"sk": "neutrál", "en": "neutral", "ja": "ふつう", "zh": "一般", "ru": "нейтрально", "es": "neutral", "de": "neutral", "fr": "neutre", "pt": "neutro"},
    "session.felt.valence.1": {"sk": "skôr dobre", "en": "rather good", "ja": "やや良い", "zh": "偏好", "ru": "скорее хорошо", "es": "algo bien", "de": "eher gut", "fr": "plutôt bien", "pt": "algo bom"},
    "session.felt.valence.2": {"sk": "dobre", "en": "good", "ja": "良い", "zh": "好", "ru": "хорошо", "es": "bien", "de": "gut", "fr": "bien", "pt": "bom"},
    "session.felt.body_q": {"sk": "Keď to bolo najintenzívnejšie, telo bolo skôr…", "en": "At the most intense moment, your body was…", "ja": "一番きつかったとき、体はどうだった…", "zh": "最紧张的时候，身体更偏…", "ru": "В самый напряжённый момент тело было скорее…", "es": "En el momento más intenso, tu cuerpo estaba…", "de": "Im intensivsten Moment war dein Körper eher…", "fr": "Au moment le plus intense, ton corps était plutôt…", "pt": "No momento mais intenso, o corpo estava antes…"},
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
    "history.export_col.body_peak": {"sk": "telo v špičke", "en": "body at peak", "ja": "ピーク時の体", "zh": "峰值身体", "ru": "тело на пике", "es": "cuerpo en pico", "de": "Körper im Peak", "fr": "corps au pic", "pt": "corpo no pico"},
    "history.export_col.cue_verdict": {"sk": "hláška verdikt", "en": "cue verdict", "ja": "合図の評価", "zh": "提示评价", "ru": "вердикт подсказки", "es": "veredicto aviso", "de": "Hinweis-Urteil", "fr": "verdict signal", "pt": "veredito aviso"},
    "history.export_col.confounded": {"sk": "skreslená?", "en": "confounded?", "ja": "撹乱？", "zh": "受干扰？", "ru": "искажена?", "es": "sesgada?", "de": "verfälscht?", "fr": "faussée ?", "pt": "enviesada?"},
}
for _k, _langs in _DOPLNENE_PREKLADY.items():
    STRINGS.setdefault(_k, {}).update(_langs)

STRINGS.setdefault("app.version_short", {}).update({
    "ja": "アルファ 0.1", "zh": "Alpha 0.1", "ru": "альфа 0.1",
    "es": "alfa 0.1", "pt": "alfa 0.1",
})
