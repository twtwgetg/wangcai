import json
import os
import pickle
import re
import jieba

MODEL_DIR = os.path.join(os.path.dirname(__file__), "model")
MODEL_PATH = os.path.join(MODEL_DIR, "intent_classifier.pkl")
VECTORIZER_PATH = os.path.join(MODEL_DIR, "vectorizer.pkl")
LABEL_PATH = os.path.join(MODEL_DIR, "label_names.json")

_clf = None
_vectorizer = None
_label_names = None


def _load():
    global _clf, _vectorizer, _label_names
    if _clf is None:
        with open(MODEL_PATH, "rb") as f:
            _clf = pickle.load(f)
        with open(VECTORIZER_PATH, "rb") as f:
            _vectorizer = pickle.load(f)
        with open(LABEL_PATH, "r", encoding="utf-8") as f:
            _label_names = json.load(f)


def _preprocess(text):
    text = text.lower()
    text = re.sub(r"[a-z]:[\\/]", " DISK ", text)
    text = re.sub(r"[\\/]", " ", text)
    text = re.sub(r"[^\u4e00-\u9fff\w\s]", " ", text)
    words = jieba.lcut(text)
    return " ".join(w.strip() for w in words if w.strip())


def predict(message, threshold=0.6):
    _load()
    processed = _preprocess(message)
    X = _vectorizer.transform([processed])
    probs = _clf.predict_proba(X)[0]
    best_idx = probs.argmax()
    confidence = float(probs[best_idx])
    intent = _label_names[best_idx] if confidence >= threshold else None
    return {
        "intent": intent,
        "confidence": confidence,
        "all_probs": {_label_names[i]: float(probs[i]) for i in range(len(_label_names))},
    }


def predict_intent(message, threshold=0.6):
    result = predict(message, threshold)
    return result["intent"], result["confidence"], result["all_probs"]
