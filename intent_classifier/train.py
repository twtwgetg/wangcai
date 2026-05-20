import json
import os
import pickle
import re

import jieba
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "intents.json")
MODEL_DIR = os.path.join(os.path.dirname(__file__), "model")
MODEL_PATH = os.path.join(MODEL_DIR, "intent_classifier.pkl")
VECTORIZER_PATH = os.path.join(MODEL_DIR, "vectorizer.pkl")


def load_data(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    texts = []
    labels = []
    label_names = list(data["intents"].keys())

    for intent_name, intent_data in data["intents"].items():
        for example in intent_data["examples"]:
            texts.append(example)
            labels.append(intent_name)

    return texts, labels, label_names


def preprocess(text):
    text = text.lower()
    text = re.sub(r"[a-z]:[\\/]", " DISK ", text)
    text = re.sub(r"[\\/]", " ", text)
    text = re.sub(r"[^\u4e00-\u9fff\w\s]", " ", text)
    words = jieba.lcut(text)
    return " ".join(w.strip() for w in words if w.strip())


def augment(text, label):
    results = [text]
    prefixes = ["请帮我", "帮我", "给我", "麻烦"]
    for p in prefixes:
        if p not in text:
            results.append(p + text)
    return results


def train():
    texts, labels, label_names = load_data(DATA_PATH)

    augmented_texts = []
    augmented_labels = []
    for t, l in zip(texts, labels):
        for variant in augment(t, l):
            augmented_texts.append(preprocess(variant))
            augmented_labels.append(l)

    vectorizer = TfidfVectorizer(ngram_range=(1, 3), max_features=5000, token_pattern=r"(?u)\S+")
    X = vectorizer.fit_transform(augmented_texts)
    y = augmented_labels

    clf = LogisticRegression(max_iter=1000, C=2.0)
    clf.fit(X, y)

    scores = cross_val_score(clf, X, y, cv=5)
    print(f"Cross-val accuracy: {scores.mean():.3f} (+/- {scores.std():.3f})")

    preds = clf.predict(X)
    correct = sum(1 for a, b in zip(preds, y) if a == b)
    print(f"Train accuracy: {correct}/{len(y)} = {correct / len(y):.3f}")

    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(clf, f)
    with open(VECTORIZER_PATH, "wb") as f:
        pickle.dump(vectorizer, f)

    with open(os.path.join(MODEL_DIR, "label_names.json"), "w", encoding="utf-8") as f:
        json.dump(list(clf.classes_), f, ensure_ascii=False)

    print(f"Model saved to {MODEL_PATH}")
    print(f"Vectorizer saved to {VECTORIZER_PATH}")

    print("\nIntent categories:")
    for name in sorted(label_names):
        count = labels.count(name)
        print(f"  {name}: {count} examples")


if __name__ == "__main__":
    train()
