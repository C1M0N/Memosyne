from jsonschema import Draft202012Validator

def build_schema(cnTags: list[str]) -> dict:
  return {
    "type": "object",
    "properties": {
      "IPA": {
        "type": "string",
        "description": "American IPA between slashes; empty only if POS='abbr.'.",
        "pattern": r"^(\/[^\s\/].*\/|)$"
      },
      "POS": {"type": "string", "enum": ["n.","vt.","vi.","adj.","adv.","P.","O.","abbr."]},
      "Tag": {"type": "string", "enum": cnTags + [""]},
      "Rarity": {"type": "string", "enum": ["", "RARE"]},
      "EnDef": {"type": "string"},
      "PPfix": {"type": "string"},
      "PPmeans": {"type": "string", "pattern": r"^[\x20-\x7E]*$"}
    },
    "required": ["IPA","POS","Tag","Rarity","EnDef","PPfix","PPmeans"],
    "additionalProperties": False
  }

def validate_payload(obj: dict, schema: dict) -> list[str]:
  errors = []
  v = Draft202012Validator(schema)
  for e in v.iter_errors(obj):
    errors.append(e.message)
  return errors