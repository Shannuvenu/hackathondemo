from deepface import DeepFace
import cv2

def detect_emotion(frame):
    result = DeepFace.analyze(frame, actions=['emotion'])
    return result[0]['dominant_emotion']
