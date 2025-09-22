"""Multi-column reflow utilities for layout transformation.

This module implements experimental multi-column reflow using heuristics
to detect 2-3 column layouts and reorder blocks for better reading flow.
"""

from __future__ import annotations

import logging
import math
from typing import Any

logger = logging.getLogger(__name__)


def _block_x_center(block: object) -> float | None:
    """Try to compute the horizontal center of a block using its bbox."""
    bbox = getattr(block, "bbox", None) or getattr(block, "bounding_box", None)
    if not bbox:
        # Sometimes bbox may be an object with attributes x0/x1
        x0 = getattr(block, "x0", None)
        x1 = getattr(block, "x1", None)
        if isinstance(x0, int | float) and isinstance(x1, int | float):
            return (float(x0) + float(x1)) / 2.0
        return None

    # bbox could be a tuple (x0, y0, x1, y1) or an object with fields
    if isinstance(bbox, list | tuple) and len(bbox) >= 4:
        x0, _, x1, _ = bbox[:4]
        try:
            return (float(x0) + float(x1)) / 2.0
        except Exception:
            return None

    x0 = getattr(bbox, "x0", None)
    x1 = getattr(bbox, "x1", None)
    if isinstance(x0, int | float) and isinstance(x1, int | float):
        return (float(x0) + float(x1)) / 2.0

    return None


def _block_y_top(block: object) -> float | None:
    """Try to compute the top y-coordinate of a block using its bbox."""
    bbox = getattr(block, "bbox", None) or getattr(block, "bounding_box", None)
    if not bbox:
        # Sometimes bbox may be an object with attributes y0
        y0 = getattr(block, "y0", None)
        if isinstance(y0, int | float):
            return float(y0)
        return None

    # bbox could be a tuple (x0, y0, x1, y1) or an object with fields
    if isinstance(bbox, list | tuple) and len(bbox) >= 4:
        _, y0, _, _ = bbox[:4]
        try:
            return float(y0)
        except Exception:
            return None

    y0 = getattr(bbox, "y0", None)
    if isinstance(y0, int | float):
        return float(y0)

    return None


def _block_type(block: object) -> str:
    """Try to determine the type/category of a block."""
    # Try common attribute names for block type
    block_type = getattr(block, "type", None) or getattr(block, "category", None)
    if block_type is not None:
        # Handle callable attributes (like methods that return the type)
        if callable(block_type):
            try:
                block_type = block_type()
            except Exception:
                block_type = None

        if block_type is not None:
            return str(block_type).lower()

    # Default to "text" if we can't determine the type
    return "text"


def _simple_kmeans(points: list[float], k: int, max_iterations: int = 100) -> tuple[list[int], list[float]]:
    """Simple k-means clustering implementation.

    Args:
        points: List of 1D points to cluster
        k: Number of clusters
        max_iterations: Maximum iterations

    Returns:
        Tuple of (cluster_assignments, centroids)
    """
    if len(points) < k:
        # Not enough points for k clusters
        return list(range(len(points))), points[:]

    # Initialize centroids by spreading them across the range
    min_point = min(points)
    max_point = max(points)
    if max_point == min_point:
        # All points are the same
        return [0] * len(points), [min_point]

    centroids = []
    for i in range(k):
        centroid = min_point + (max_point - min_point) * i / (k - 1)
        centroids.append(centroid)

    assignments = [0] * len(points)

    for _ in range(max_iterations):
        # Assign points to nearest centroid
        new_assignments = []
        for point in points:
            distances = [abs(point - centroid) for centroid in centroids]
            new_assignments.append(distances.index(min(distances)))

        # Check for convergence
        if new_assignments == assignments:
            break

        assignments = new_assignments

        # Update centroids
        new_centroids = []
        for i in range(k):
            cluster_points = [points[j] for j in range(len(points)) if assignments[j] == i]
            if cluster_points:
                new_centroids.append(sum(cluster_points) / len(cluster_points))
            else:
                new_centroids.append(centroids[i])  # Keep old centroid if cluster is empty

        centroids = new_centroids

    return assignments, centroids


def _silhouette_score(points: list[float], assignments: list[int], centroids: list[float]) -> float:
    """Calculate silhouette score for clustering quality.

    Args:
        points: Original points
        assignments: Cluster assignments for each point
        centroids: Cluster centroids

    Returns:
        Silhouette score (higher is better, range roughly [-1, 1])
    """
    if len(set(assignments)) < 2:
        return 0.0  # Only one cluster

    silhouette_values = []

    for i, point in enumerate(points):
        cluster = assignments[i]

        # Calculate average distance to points in same cluster (a)
        same_cluster_points = [points[j] for j in range(len(points)) if assignments[j] == cluster and j != i]
        if same_cluster_points:
            a = sum(abs(point - other) for other in same_cluster_points) / len(same_cluster_points)
        else:
            a = 0.0

        # Calculate minimum average distance to points in other clusters (b)
        other_clusters = set(assignments) - {cluster}
        if not other_clusters:
            silhouette_values.append(0.0)
            continue

        min_b = float("inf")
        for other_cluster in other_clusters:
            other_cluster_points = [points[j] for j in range(len(points)) if assignments[j] == other_cluster]
            if other_cluster_points:
                avg_dist = sum(abs(point - other) for other in other_cluster_points) / len(other_cluster_points)
                min_b = min(min_b, avg_dist)

        b = min_b if min_b != float("inf") else 0.0

        # Calculate silhouette value
        if max(a, b) > 0:
            silhouette_values.append((b - a) / max(a, b))
        else:
            silhouette_values.append(0.0)

    return sum(silhouette_values) / len(silhouette_values) if silhouette_values else 0.0


def _detect_columns_kmeans(x_centers: list[float]) -> tuple[int, list[int], list[float]] | None:
    """Detect columns using k-means clustering with silhouette score validation.

    Args:
        x_centers: List of x-center coordinates

    Returns:
        Tuple of (num_columns, assignments, centroids) or None if no good clustering found
    """
    best_k = 1
    best_score = -1.0
    best_assignments = []
    best_centroids = []

    # Try k=2 and k=3
    for k in [2, 3]:
        if len(x_centers) < k * 2:  # Need at least 2 points per cluster
            continue

        assignments, centroids = _simple_kmeans(x_centers, k)
        score = _silhouette_score(x_centers, assignments, centroids)

        if score > best_score and score > 0.2:  # Threshold for good clustering
            best_k = k
            best_score = score
            best_assignments = assignments
            best_centroids = centroids

    if best_k > 1 and best_score > 0.2:
        return best_k, best_assignments, best_centroids

    return None


def _detect_columns_histogram(x_centers: list[float], page_width: float) -> tuple[int, list[float]] | None:
    """Detect columns using histogram valley detection.

    Args:
        x_centers: List of x-center coordinates
        page_width: Width of the page

    Returns:
        Tuple of (num_columns, column_boundaries) or None if no columns detected
    """
    if len(x_centers) < 8:
        return None

    # Create histogram with reasonable number of bins
    num_bins = min(20, len(x_centers) // 2)
    min_x = min(x_centers)
    max_x = max(x_centers)

    if max_x <= min_x:
        return None

    bin_width = (max_x - min_x) / num_bins
    bins = [0] * num_bins

    # Fill histogram
    for x in x_centers:
        bin_idx = min(int((x - min_x) / bin_width), num_bins - 1)
        bins[bin_idx] += 1

    # Find valleys (local minima)
    valleys = []
    for i in range(1, len(bins) - 1):
        if bins[i] < bins[i - 1] and bins[i] < bins[i + 1] and bins[i] == 0:
            valley_x = min_x + (i + 0.5) * bin_width
            valleys.append(valley_x)

    if len(valleys) >= 1:
        # Check if valley creates reasonable column separation
        valley = valleys[0]  # Use first valley for 2-column detection

        left_points = [x for x in x_centers if x < valley]
        right_points = [x for x in x_centers if x > valley]

        if len(left_points) >= 3 and len(right_points) >= 3:
            # Check gap size
            gap_size = min(right_points) - max(left_points)
            if gap_size >= 0.08 * page_width:
                return 2, [valley]

    return None


def reflow_columns(page_blocks: list[Any], page_width: float) -> list[Any]:
    """Reorder multi-column page blocks into natural reading order.

    This function implements experimental multi-column reflow using heuristics
    to detect 2-3 column layouts and reorder blocks for better reading flow.

    Args:
        page_blocks: List of block objects from the page
        page_width: Width of the page in points

    Returns:
        List of blocks in reordered reading order, or original order if reflow fails

    Algorithm:
    1. Extract x-midpoints of text blocks
    2. Try k-means clustering (k=2,3) with silhouette score validation
    3. Fallback to histogram valley detection
    4. Verify column separation and uniformity
    5. Assign blocks to columns and sort within columns by y-coordinate
    6. Preserve non-text elements in appropriate positions
    """

    if len(page_blocks) < 6:
        logger.debug("Too few blocks (%d) for column reflow", len(page_blocks))
        return page_blocks

    # Extract text blocks and their x-centers
    text_blocks = []
    text_x_centers = []

    for block in page_blocks:
        block_type = _block_type(block)
        x_center = _block_x_center(block)

        if block_type == "text" and x_center is not None:
            text_blocks.append(block)
            text_x_centers.append(x_center)

    if len(text_x_centers) < 6:
        logger.debug("Too few text blocks (%d) for column reflow", len(text_x_centers))
        return page_blocks

    # Try k-means clustering first
    kmeans_result = _detect_columns_kmeans(text_x_centers)

    if kmeans_result is not None:
        num_columns, assignments, centroids = kmeans_result
        logger.debug("K-means detected %d columns", num_columns)

        # Verify column separation
        sorted_centroids = sorted(centroids)
        min_gap = float("inf")
        for i in range(1, len(sorted_centroids)):
            gap = sorted_centroids[i] - sorted_centroids[i - 1]
            min_gap = min(min_gap, gap)

        if min_gap < 0.08 * page_width:
            logger.debug("Column gap too small (%.1f < %.1f), skipping reflow", min_gap, 0.08 * page_width)
            return page_blocks

        # Check column width uniformity
        if num_columns >= 2:
            widths = []
            for i, _centroid in enumerate(sorted_centroids):
                cluster_points = [text_x_centers[j] for j in range(len(text_x_centers)) if assignments[j] == i]
                if len(cluster_points) >= 2:
                    width = max(cluster_points) - min(cluster_points)
                    widths.append(width)

            if len(widths) >= 2:
                mean_width = sum(widths) / len(widths)
                if mean_width > 0:
                    std_dev = math.sqrt(sum((w - mean_width) ** 2 for w in widths) / len(widths))
                    uniformity = std_dev / mean_width
                    if uniformity > 0.25:
                        logger.debug("Column widths not uniform (%.2f > 0.25), skipping reflow", uniformity)
                        return page_blocks

        # Assign all blocks to columns based on x-center
        block_columns = []
        for block in page_blocks:
            x_center = _block_x_center(block)
            if x_center is not None:
                # Find closest centroid
                distances = [abs(x_center - c) for c in centroids]
                column = distances.index(min(distances))
                block_columns.append((block, column))
            else:
                # Non-positioned blocks go to column 0
                block_columns.append((block, 0))

    else:
        # Fallback to histogram valley detection
        histogram_result = _detect_columns_histogram(text_x_centers, page_width)

        if histogram_result is None:
            logger.debug("No columns detected by histogram method")
            return page_blocks

        num_columns, boundaries = histogram_result
        logger.debug("Histogram detected %d columns", num_columns)

        # Assign blocks to columns based on boundaries
        block_columns = []
        for block in page_blocks:
            x_center = _block_x_center(block)
            if x_center is not None:
                column = 0
                for boundary in boundaries:
                    if x_center > boundary:
                        column += 1
                block_columns.append((block, column))
            else:
                block_columns.append((block, 0))

    # Group blocks by column and sort within each column by y-coordinate
    columns_dict: dict[int, list[Any]] = {}
    for block, column in block_columns:
        if column not in columns_dict:
            columns_dict[column] = []
        columns_dict[column].append(block)

    # Sort blocks within each column by y-coordinate (top to bottom)
    for column_blocks in columns_dict.values():
        column_blocks.sort(key=lambda b: _block_y_top(b) or 0.0)

    # Concatenate columns left-to-right
    reordered_blocks = []
    for column in sorted(columns_dict.keys()):
        reordered_blocks.extend(columns_dict[column])

    logger.debug("Reordered %d blocks into %d columns", len(page_blocks), num_columns)
    return reordered_blocks
