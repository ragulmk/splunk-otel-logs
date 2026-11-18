#!/usr/bin/env python3
"""Offline checks for config files (runs in CI, no Splunk needed)."""
import configparser
import glob
import json
import sys
import xml.dom.minidom

import yaml

failed = False


def check(label, fn, path):
    global failed
    try:
        fn(path)
        print(f"ok    {label:9} {path}")
    except Exception as exc:  # noqa: BLE001
        failed = True
        print(f"FAIL  {label:9} {path}: {exc}")


def splunk_conf(path):
    # Splunk .conf files are INI-like; join backslash line continuations first.
    text = open(path).read().replace("\\\n", " ")
    text = text.replace("\n[]\n", "\n[_global]\n")  # "[]" is Splunk's global stanza
    cp = configparser.RawConfigParser(strict=True, delimiters=("=",), comment_prefixes=("#",))
    cp.optionxform = str
    cp.read_string(text)


def saved_searches(path):
    splunk_conf(path)
    cp = configparser.RawConfigParser(strict=True, delimiters=("=",), comment_prefixes=("#",))
    cp.optionxform = str
    cp.read_string(open(path).read().replace("\\\n", " "))
    for name in cp.sections():
        if "search" not in cp[name]:
            raise ValueError(f"[{name}] has no search")
        if name.startswith("Alert") and cp[name].get("enableSched") != "1":
            raise ValueError(f"[{name}] is an alert but not scheduled")


for f in glob.glob("splunk/**/*.conf", recursive=True) + glob.glob("splunk/**/*.meta", recursive=True):
    check("conf", saved_searches if f.endswith("savedsearches.conf") else splunk_conf, f)
for f in glob.glob("splunk/**/*.xml", recursive=True):
    check("xml", xml.dom.minidom.parse, f)
for f in glob.glob("**/*.y*ml", recursive=True) + glob.glob(".github/workflows/*.yml"):
    check("yaml", lambda p: yaml.safe_load(open(p)), f)
for f in glob.glob("grafana/dashboards/*.json"):
    check("json", lambda p: json.load(open(p)), f)

sys.exit(1 if failed else 0)
