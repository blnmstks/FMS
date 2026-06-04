DEFINE_BRAND_ID_PROMPT = (
    "Analyze:\n"
    "Name style and naming logic\n"
    "Visual identity (colors, typography, logo feel)\n"
    "Banner composition and tone\n"
    "Channel description language + positioning\n"
    "Target audience signal\n\n"
    "Then output only valid JSON (no commentary, no markdown):\n"
    "{\n"
    '  "channel_name_variants": ["name1", "name2", "name3", "name4", "name5"],\n'
    '  "channel_description_variants": ["description1", "description2"],\n'
    '  "channel_avatar_prompt": "logo generation prompt",\n'
    '  "channel_banner_prompt": "banner generation prompt"\n'
    "}"
)
