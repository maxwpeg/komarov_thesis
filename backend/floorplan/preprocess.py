"""Image preprocessing: rectification, deskewing, binarization."""

import cv2
import numpy as np
from typing import Tuple, Optional


class Config:
    CANNY_THRESHOLD1 = 50
    CANNY_THRESHOLD2 = 150

    MIN_CONTOUR_AREA_RATIO = 0.2   # relative to image area
    CORNER_EPSILON = 0.02

    DESKEW_ANGLE_RANGE = 3

    BG_BLUR_SIZE = 51
    ADAPTIVE_BLOCK_SIZE = 41
    ADAPTIVE_C = 10

    MORPH_KERNEL_SIZE = 3
    MIN_COMPONENT_AREA = 20


def order_corners(pts: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1)

    rect[0] = pts[np.argmin(s)]   # top-left
    rect[2] = pts[np.argmax(s)]   # bottom-right
    rect[1] = pts[np.argmin(diff)]  # top-right
    rect[3] = pts[np.argmax(diff)]  # bottom-left
    return rect


def rectify_document(img: np.ndarray) -> Tuple[np.ndarray, Optional[np.ndarray]]:
    if img is None or img.size == 0:
        return img, None

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    edges = cv2.Canny(gray, Config.CANNY_THRESHOLD1, Config.CANNY_THRESHOLD2)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    edges = cv2.dilate(edges, kernel, iterations=2)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return img, None

    img_area = img.shape[0] * img.shape[1]
    min_area = img_area * Config.MIN_CONTOUR_AREA_RATIO

    candidates = sorted(contours, key=cv2.contourArea, reverse=True)

    for contour in candidates[:10]:
        area = cv2.contourArea(contour)
        if area < min_area:
            continue

        epsilon = Config.CORNER_EPSILON * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)

        if len(approx) == 4:
            pts = approx.reshape(4, 2).astype(np.float32)
        else:
            rect = cv2.minAreaRect(contour)
            pts = cv2.boxPoints(rect).astype(np.float32)

        rect_pts = order_corners(pts)

        width = int(max(
            np.linalg.norm(rect_pts[1] - rect_pts[0]),
            np.linalg.norm(rect_pts[2] - rect_pts[3])
        ))
        height = int(max(
            np.linalg.norm(rect_pts[3] - rect_pts[0]),
            np.linalg.norm(rect_pts[2] - rect_pts[1])
        ))

        if width < 100 or height < 100:
            continue

        dst_pts = np.array(
            [[0, 0], [width, 0], [width, height], [0, height]],
            dtype=np.float32
        )

        M = cv2.getPerspectiveTransform(rect_pts, dst_pts)
        rectified = cv2.warpPerspective(img, M, (width, height))
        return rectified, M

    return img, None


def deskew(img: np.ndarray) -> np.ndarray:
    if img is None or img.size == 0:
        return img

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    edges = cv2.Canny(gray, 80, 200)

    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=100,
        minLineLength=150,
        maxLineGap=10
    )

    if lines is None:
        return img

    angles = []
    for l in lines[:, 0]:
        x1, y1, x2, y2 = l
        dx = x2 - x1
        dy = y2 - y1
        length = np.hypot(dx, dy)
        if length < 150:
            continue

        angle = np.degrees(np.arctan2(dy, dx)) % 180

        # only near-horizontal lines for skew estimation
        if angle < 10 or angle > 170:
            if angle > 170:
                angle -= 180
            angles.append(angle)

    if not angles:
        return img

    skew = float(np.median(angles))
    if abs(skew) > Config.DESKEW_ANGLE_RANGE:
        return img

    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), skew, 1.0)
    return cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REFLECT)


def remove_small_components(binary: np.ndarray, min_area: int) -> np.ndarray:
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    cleaned = np.zeros_like(binary)

    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if area >= min_area:
            cleaned[labels == i] = 255

    return cleaned


def binarize(img: np.ndarray) -> np.ndarray:
    if img is None or img.size == 0:
        return img

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    gray = cv2.medianBlur(gray, 5)

    bg = cv2.GaussianBlur(gray, (Config.BG_BLUR_SIZE, Config.BG_BLUR_SIZE), 0)
    norm = cv2.divide(gray, bg, scale=255)

    binary = cv2.adaptiveThreshold(
        norm,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        Config.ADAPTIVE_BLOCK_SIZE,
        Config.ADAPTIVE_C
    )

    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (Config.MORPH_KERNEL_SIZE, Config.MORPH_KERNEL_SIZE)
    )

    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)

    binary = remove_small_components(binary, Config.MIN_COMPONENT_AREA)

    return binary


def preprocess(img_path: str, rectify: bool = True, deskew_enabled: bool = False) -> Tuple[np.ndarray, np.ndarray]:
    img = cv2.imread(img_path)
    if img is None:
        raise ValueError(f"Cannot read image: {img_path}")

    if rectify:
        img, _ = rectify_document(img)

    if deskew_enabled:
        img = deskew(img)

    binary = binarize(img)
    return binary, img