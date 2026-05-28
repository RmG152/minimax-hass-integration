"""Constants for MiniMax integration."""

import logging

from homeassistant.const import Platform

DOMAIN = "minimax"
LOGGER = logging.getLogger(__package__)

DEFAULT_TITLE = "MiniMax"
DEFAULT_CONVERSATION_NAME = "MiniMax Conversation"
DEFAULT_STT_NAME = "MiniMax STT"
DEFAULT_TTS_NAME = "MiniMax TTS"
DEFAULT_AI_TASK_NAME = "MiniMax AI Task"

PLATFORMS = (
    Platform.CONVERSATION,
    Platform.STT,
    Platform.TTS,
    Platform.AI_TASK,
)

MINIMAX_ANTHROPIC_API_URL = "https://api.minimax.io/anthropic/v1/messages"
MINIMAX_TTS_API = "https://api.minimax.io/v1/t2a_v2"
MINIMAX_STT_API = "https://api.minimax.io/v1/audio/transcription"
MINIMAX_IMAGE_API = "https://api.minimax.io/v1/image_generation"

CONF_API_KEY = "api_key"
CONF_RECOMMENDED = "recommended"
CONF_PROMPT = "prompt"
CONF_CHAT_MODEL = "chat_model"
CONF_VOICE_ID = "voice_id"

RECOMMENDED_CHAT_MODEL = "MiniMax-M2.7"
RECOMMENDED_TTS_MODEL = "speech-2.8-hd"
RECOMMENDED_STT_MODEL = "MiniMax-M2.7"
RECOMMENDED_IMAGE_MODEL = "image-01"
RECOMMENDED_AI_TASK_MAX_TOKENS = 16000
AI_TASK_TIMEOUT = 120

CHAT_MODELS = [
    {"label": "MiniMax-M2.7 (Recommended)", "value": "MiniMax-M2.7"},
    {
        "label": "MiniMax-M2.7-highspeed (Fast)",
        "value": "MiniMax-M2.7-highspeed",
    },
    {"label": "MiniMax-M2.5", "value": "MiniMax-M2.5"},
    {
        "label": "MiniMax-M2.5-highspeed (Fast)",
        "value": "MiniMax-M2.5-highspeed",
    },
    {"label": "MiniMax-M2.1", "value": "MiniMax-M2.1"},
    {
        "label": "MiniMax-M2.1-highspeed (Fast)",
        "value": "MiniMax-M2.1-highspeed",
    },
    {"label": "MiniMax-M2", "value": "MiniMax-M2"},
]


CONF_SPEED = "speed"
CONF_VOL = "vol"
CONF_PITCH = "pitch"
DEFAULT_SPEED = 1.0
DEFAULT_VOL = 1.0
DEFAULT_PITCH = 0

CONF_CONVERSATION_TTS_ENABLED = "conversation_tts_enabled"
DEFAULT_CONVERSATION_TTS_ENABLED = True

CONF_CONVERSATION_MAX_TOKENS = "conversation_max_tokens"
DEFAULT_CONVERSATION_MAX_TOKENS = 16000
DEFAULT_MIN_MAX_TOKENS = 1000

CONF_CONVERSATION_EXPIRY_MINUTES = "conversation_expiry_minutes"
DEFAULT_CONVERSATION_EXPIRY_MINUTES = 5

CONF_MAX_CONVERSATIONS = "max_conversations"
DEFAULT_MAX_CONVERSATIONS = 50

CONF_MEMORY_ENABLED = "memory_enabled"
DEFAULT_MEMORY_ENABLED = True

CONF_MEMORY_MAX_COUNT = "memory_max_count"
DEFAULT_MEMORY_MAX_COUNT = 50

CONF_MEMORY_EXPIRY_DAYS = "memory_expiry_days"
DEFAULT_MEMORY_EXPIRY_DAYS = 30

MEMORY_CATEGORIES = [
    "name",
    "preference",
    "habit",
    "device",
    "other",
]

SUPPORTED_LANGUAGES = [
    "en-US",
    "zh-CN",
    "ja-JP",
    "yue-CN",
    "ko-KR",
    "es-ES",
    "pt-PT",
    "fr-FR",
    "id-ID",
    "de-DE",
    "ru-RU",
    "it-IT",
    "nl-NL",
    "vi-VN",
    "ar-SA",
    "tr-TR",
    "uk-UA",
    "th-TH",
    "pl-PL",
    "ro-RO",
    "el-GR",
    "cs-CZ",
    "fi-FI",
    "hi-IN",
]

LANGUAGE_NAMES = {
    "en-US": "English",
    "zh-CN": "Chinese",
    "ja-JP": "Japanese",
    "yue-CN": "Cantonese",
    "ko-KR": "Korean",
    "es-ES": "Spanish",
    "pt-PT": "Portuguese",
    "fr-FR": "French",
    "id-ID": "Indonesian",
    "de-DE": "German",
    "ru-RU": "Russian",
    "it-IT": "Italian",
    "nl-NL": "Dutch",
    "vi-VN": "Vietnamese",
    "ar-SA": "Arabic",
    "tr-TR": "Turkish",
    "uk-UA": "Ukrainian",
    "th-TH": "Thai",
    "pl-PL": "Polish",
    "ro-RO": "Romanian",
    "el-GR": "Greek",
    "cs-CZ": "Czech",
    "fi-FI": "Finnish",
    "hi-IN": "Hindi",
}

VOICE_IDS = {
    "en-US": [
        "English_expressive_narrator",
        "English_radiant_girl",
        "English_magnetic_voiced_man",
        "English_compelling_lady1",
        "English_Aussie_Bloke",
        "English_captivating_female1",
        "English_Upbeat_Woman",
        "English_Trustworth_Man",
        "English_CalmWoman",
        "English_UpsetGirl",
        "English_Gentle-voiced_man",
        "English_Whispering_girl",
        "English_Diligent_Man",
        "English_Graceful_Lady",
        "English_ReservedYoungMan",
        "English_PlayfulGirl",
        "English_ManWithDeepVoice",
        "English_MaturePartner",
        "English_FriendlyPerson",
        "English_MatureBoss",
        "English_Debator",
        "English_LovelyGirl",
        "English_Steadymentor",
        "English_Deep-VoicedGentleman",
        "English_Wiselady",
        "English_CaptivatingStoryteller",
        "English_DecentYoungMan",
        "English_SentimentalLady",
        "English_ImposingManner",
        "English_SadTeen",
        "English_PassionateWarrior",
        "English_WiseScholar",
        "English_Soft-spokenGirl",
        "English_SereneWoman",
        "English_ConfidentWoman",
        "English_PatientMan",
        "English_Comedian",
        "English_BossyLeader",
        "English_Strong-WilledBoy",
        "English_StressedLady",
        "English_AssertiveQueen",
        "English_AnimeCharacter",
        "English_Jovialman",
        "English_WhimsicalGirl",
        "English_Kind-heartedGirl",
    ],
    "zh-CN": [
        "Chinese (Mandarin)_Reliable_Executive",
        "Chinese (Mandarin)_News_Anchor",
        "Chinese (Mandarin)_Unrestrained_Young_Man",
        "Chinese (Mandarin)_Mature_Woman",
        "Arrogant_Miss",
        "Robot_Armor",
        "Chinese (Mandarin)_Kind-hearted_Antie",
        "Chinese (Mandarin)_HK_Flight_Attendant",
        "Chinese (Mandarin)_Humorous_Elder",
        "Chinese (Mandarin)_Gentleman",
        "Chinese (Mandarin)_Warm_Bestie",
        "Chinese (Mandarin)_Stubborn_Friend",
        "Chinese (Mandarin)_Sweet_Lady",
        "Chinese (Mandarin)_Southern_Young_Man",
        "Chinese (Mandarin)_Wise_Women",
        "Chinese (Mandarin)_Gentle_Youth",
        "Chinese (Mandarin)_Warm_Girl",
        "Chinese (Mandarin)_Male_Announcer",
        "Chinese (Mandarin)_Kind-hearted_Elder",
        "Chinese (Mandarin)_Cute_Spirit",
        "Chinese (Mandarin)_Radio_Host",
        "Chinese (Mandarin)_Lyrical_Voice",
        "Chinese (Mandarin)_Straightforward_Boy",
        "Chinese (Mandarin)_Sincere_Adult",
        "Chinese (Mandarin)_Gentle_Senior",
        "Chinese (Mandarin)_Crisp_Girl",
        "Chinese (Mandarin)_Pure-hearted_Boy",
        "Chinese (Mandarin)_Soft_Girl",
        "Chinese (Mandarin)_IntellectualGirl",
        "Chinese (Mandarin)_Warm_HeartedGirl",
        "Chinese (Mandarin)_Laid_BackGirl",
        "Chinese (Mandarin)_ExplorativeGirl",
        "Chinese (Mandarin)_Warm-HeartedAunt",
        "Chinese (Mandarin)_BashfulGirl",
    ],
    "ja-JP": [
        "Japanese_IntellectualSenior",
        "Japanese_DecisivePrincess",
        "Japanese_LoyalKnight",
        "Japanese_DominantMan",
        "Japanese_SeriousCommander",
        "Japanese_ColdQueen",
        "Japanese_DependableWoman",
        "Japanese_GentleButler",
        "Japanese_KindLady",
        "Japanese_CalmLady",
        "Japanese_OptimisticYouth",
        "Japanese_GenerousIzakayaOwner",
        "Japanese_SportyStudent",
        "Japanese_InnocentBoy",
        "Japanese_GracefulMaiden",
    ],
    "yue-CN": [
        "Cantonese_ProfessionalHost (F)",
        "Cantonese_GentleLady",
        "Cantonese_ProfessionalHost (M)",
        "Cantonese_PlayfulMan",
        "Cantonese_CuteGirl",
        "Cantonese_KindWoman",
    ],
    "ko-KR": [
        "Korean_AirheadedGirl",
        "Korean_AthleticGirl",
        "Korean_AthleticStudent",
        "Korean_BraveAdventurer",
        "Korean_BraveFemaleWarrior",
        "Korean_BraveYouth",
        "Korean_CalmGentleman",
        "Korean_CalmLady",
        "Korean_CaringWoman",
        "Korean_CharmingElderSister",
        "Korean_CharmingSister",
        "Korean_CheerfulBoyfriend",
        "Korean_CheerfulCoolJunior",
        "Korean_CheerfulLittleSister",
        "Korean_ChildhoodFriendGirl",
        "Korean_CockyGuy",
        "Korean_ColdGirl",
        "Korean_ColdYoungMan",
        "Korean_ConfidentBoss",
        "Korean_ConsiderateSenior",
        "Korean_DecisiveQueen",
        "Korean_DominantMan",
        "Korean_ElegantPrincess",
        "Korean_EnchantingSister",
        "Korean_EnthusiasticTeen",
        "Korean_FriendlyBigSister",
        "Korean_GentleBoss",
        "Korean_GentleWoman",
        "Korean_HaughtyLady",
        "Korean_InnocentBoy",
        "Korean_IntellectualMan",
        "Korean_IntellectualSenior",
        "Korean_LonelyWarrior",
        "Korean_MatureLady",
        "Korean_MysteriousGirl",
        "Korean_OptimisticYouth",
        "Korean_PlayboyCharmer",
        "Korean_PossessiveMan",
        "Korean_QuirkyGirl",
        "Korean_ReliableSister",
        "Korean_ReliableYouth",
        "Korean_SassyGirl",
        "Korean_ShyGirl",
        "Korean_SoothingLady",
        "Korean_StrictBoss",
        "Korean_SweetGirl",
        "Korean_ThoughtfulWoman",
        "Korean_WiseElf",
        "Korean_WiseTeacher",
    ],
    "es-ES": [
        "Spanish_SereneWoman",
        "Spanish_MaturePartner",
        "Spanish_CaptivatingStoryteller",
        "Spanish_Narrator",
        "Spanish_WiseScholar",
        "Spanish_Kind-heartedGirl",
        "Spanish_DeterminedManager",
        "Spanish_BossyLeader",
        "Spanish_ReservedYoungMan",
        "Spanish_ConfidentWoman",
        "Spanish_ThoughtfulMan",
        "Spanish_Strong-WilledBoy",
        "Spanish_SophisticatedLady",
        "Spanish_RationalMan",
        "Spanish_AnimeCharacter",
        "Spanish_Deep-tonedMan",
        "Spanish_Fussyhostess",
        "Spanish_SincereTeen",
        "Spanish_FrankLady",
        "Spanish_Comedian",
        "Spanish_Debator",
        "Spanish_ToughBoss",
        "Spanish_Wiselady",
        "Spanish_Steadymentor",
        "Spanish_Jovialman",
        "Spanish_SantaClaus",
        "Spanish_Rudolph",
        "Spanish_Intonategirl",
        "Spanish_Arnold",
        "Spanish_Ghost",
        "Spanish_HumorousElder",
        "Spanish_EnergeticBoy",
        "Spanish_WhimsicalGirl",
        "Spanish_StrictBoss",
        "Spanish_ReliableMan",
        "Spanish_SereneElder",
        "Spanish_AngryMan",
        "Spanish_AssertiveQueen",
        "Spanish_CaringGirlfriend",
        "Spanish_PowerfulSoldier",
        "Spanish_PassionateWarrior",
        "Spanish_ChattyGirl",
        "Spanish_RomanticHusband",
        "Spanish_CompellingGirl",
        "Spanish_PowerfulVeteran",
        "Spanish_SensibleManager",
        "Spanish_ThoughtfulLady",
    ],
    "pt-PT": [
        "Portuguese_SentimentalLady",
        "Portuguese_BossyLeader",
        "Portuguese_Wiselady",
        "Portuguese_Strong-WilledBoy",
        "Portuguese_Deep-VoicedGentleman",
        "Portuguese_UpsetGirl",
        "Portuguese_PassionateWarrior",
        "Portuguese_AnimeCharacter",
        "Portuguese_ConfidentWoman",
        "Portuguese_AngryMan",
        "Portuguese_CaptivatingStoryteller",
        "Portuguese_Godfather",
        "Portuguese_ReservedYoungMan",
        "Portuguese_SmartYoungGirl",
        "Portuguese_Kind-heartedGirl",
        "Portuguese_Pompouslady",
        "Portuguese_Grinch",
        "Portuguese_Debator",
        "Portuguese_SweetGirl",
        "Portuguese_AttractiveGirl",
        "Portuguese_ThoughtfulMan",
        "Portuguese_PlayfulGirl",
        "Portuguese_GorgeousLady",
        "Portuguese_LovelyLady",
        "Portuguese_SereneWoman",
        "Portuguese_SadTeen",
        "Portuguese_MaturePartner",
        "Portuguese_Comedian",
        "Portuguese_NaughtySchoolgirl",
        "Portuguese_Narrator",
        "Portuguese_ToughBoss",
        "Portuguese_Fussyhostess",
        "Portuguese_Dramatist",
        "Portuguese_Steadymentor",
        "Portuguese_Jovialman",
        "Portuguese_CharmingQueen",
        "Portuguese_SantaClaus",
        "Portuguese_Rudolph",
        "Portuguese_Arnold",
        "Portuguese_CharmingSanta",
        "Portuguese_CharmingLady",
        "Portuguese_Ghost",
        "Portuguese_HumorousElder",
        "Portuguese_CalmLeader",
        "Portuguese_GentleTeacher",
        "Portuguese_EnergeticBoy",
        "Portuguese_ReliableMan",
        "Portuguese_SereneElder",
        "Portuguese_GrimReaper",
        "Portuguese_AssertiveQueen",
        "Portuguese_WhimsicalGirl",
        "Portuguese_StressedLady",
        "Portuguese_FriendlyNeighbor",
        "Portuguese_CaringGirlfriend",
        "Portuguese_PowerfulSoldier",
        "Portuguese_FascinatingBoy",
        "Portuguese_RomanticHusband",
        "Portuguese_StrictBoss",
        "Portuguese_InspiringLady",
        "Portuguese_PlayfulSpirit",
        "Portuguese_ElegantGirl",
        "Portuguese_CompellingGirl",
        "Portuguese_PowerfulVeteran",
        "Portuguese_SensibleManager",
        "Portuguese_ThoughtfulLady",
        "Portuguese_TheatricalActor",
        "Portuguese_FragileBoy",
        "Portuguese_ChattyGirl",
        "Portuguese_Conscientiousinstructor",
        "Portuguese_RationalMan",
        "Portuguese_WiseScholar",
        "Portuguese_FrankLady",
        "Portuguese_DeterminedManager",
    ],
    "fr-FR": [
        "French_Male_Speech_New",
        "French_Female_News Anchor",
        "French_CasualMan",
        "French_MovieLeadFemale",
        "French_FemaleAnchor",
        "French_MaleNarrator",
    ],
    "id-ID": [
        "Indonesian_SweetGirl",
        "Indonesian_ReservedYoungMan",
        "Indonesian_CharmingGirl",
        "Indonesian_CalmWoman",
        "Indonesian_ConfidentWoman",
        "Indonesian_CaringMan",
        "Indonesian_BossyLeader",
        "Indonesian_DeterminedBoy",
        "Indonesian_GentleGirl",
    ],
    "de-DE": [
        "German_FriendlyMan",
        "German_SweetLady",
        "German_PlayfulMan",
    ],
    "ru-RU": [
        "Russian_HandsomeChildhoodFriend",
        "Russian_BrightHeroine",
        "Russian_AmbitiousWoman",
        "Russian_ReliableMan",
        "Russian_CrazyQueen",
        "Russian_PessimisticGirl",
        "Russian_AttractiveGuy",
        "Russian_Bad-temperedBoy",
    ],
    "it-IT": [
        "Italian_BraveHeroine",
        "Italian_Narrator",
        "Italian_WanderingSorcerer",
        "Italian_DiligentLeader",
    ],
    "nl-NL": [
        "Dutch_kindhearted_girl",
        "Dutch_bossy_leader",
    ],
    "vi-VN": [
        "Vietnamese_kindhearted_girl",
    ],
    "ar-SA": [
        "Arabic_CalmWoman",
        "Arabic_FriendlyGuy",
    ],
    "tr-TR": [
        "Turkish_CalmWoman",
        "Turkish_Trustworthyman",
    ],
    "uk-UA": [
        "Ukrainian_CalmWoman",
        "Ukrainian_WiseScholar",
    ],
    "th-TH": [
        "Thai_male_1_sample8",
        "Thai_male_2_sample2",
        "Thai_female_1_sample1",
        "Thai_female_2_sample2",
    ],
    "pl-PL": [
        "Polish_male_1_sample4",
        "Polish_male_2_sample3",
        "Polish_female_1_sample1",
        "Polish_female_2_sample3",
    ],
    "ro-RO": [
        "Romanian_male_1_sample2",
        "Romanian_male_2_sample1",
        "Romanian_female_1_sample4",
        "Romanian_female_2_sample1",
    ],
    "el-GR": [
        "greek_male_1a_v1",
        "Greek_female_1_sample1",
        "Greek_female_2_sample3",
    ],
    "cs-CZ": [
        "czech_male_1_v1",
        "czech_female_5_v7",
        "czech_female_2_v2",
    ],
    "fi-FI": [
        "finnish_male_3_v1",
        "finnish_male_1_v2",
        "finnish_female_4_v1",
    ],
    "hi-IN": [
        "hindi_male_1_v2",
        "hindi_female_2_v1",
        "hindi_female_1_v2",
    ],
}

RECOMMENDED_CONVERSATION_OPTIONS = {
    CONF_PROMPT: "You are EVA, a friendly Danish AI home assistant. You speak Danish. Be warm, direct and practical. Respond briefly and precisely in Danish.",
    CONF_RECOMMENDED: True,
    CONF_CONVERSATION_TTS_ENABLED: DEFAULT_CONVERSATION_TTS_ENABLED,
    CONF_MEMORY_ENABLED: DEFAULT_MEMORY_ENABLED,
    CONF_MEMORY_MAX_COUNT: DEFAULT_MEMORY_MAX_COUNT,
    CONF_MEMORY_EXPIRY_DAYS: DEFAULT_MEMORY_EXPIRY_DAYS,
}

RECOMMENDED_TTS_OPTIONS = {
    CONF_RECOMMENDED: True,
    CONF_VOICE_ID: "English_PlayfulGirl",
    CONF_SPEED: DEFAULT_SPEED,
    CONF_VOL: DEFAULT_VOL,
    CONF_PITCH: DEFAULT_PITCH,
}

RECOMMENDED_STT_OPTIONS = {
    CONF_RECOMMENDED: True,
    CONF_PROMPT: "Transcribe the attached audio",
}

RECOMMENDED_AI_TASK_OPTIONS = {
    CONF_RECOMMENDED: True,
}
