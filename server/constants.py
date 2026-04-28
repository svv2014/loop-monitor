from pathlib import Path

SUPPORTED_API_MAJOR = "1"
MONITOR_VERSION = (Path(__file__).parent.parent / "VERSION").read_text().strip() if (Path(__file__).parent.parent / "VERSION").exists() else "unknown"

PROJECTS = {
    'ppl':               'svv2014/ppl-study',
    'boba-event':        'svv2014/boba-event',
    'loop':             'svv2014/loop',
    'bounty':            'svv2014/loop-monitor',
    'vrefm-classifier':  'svv2014/vrefm-classifier',
    'pa-scanner':        'svv2014/pa-scanner',
    'ntc':               'svv2014/NanoTraderCopilot',
}

HANDLER_TIMEOUT = 30
