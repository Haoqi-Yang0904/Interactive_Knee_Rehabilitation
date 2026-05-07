import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401


# =========================
# Configurable parameters
# =========================

# theta_1 and theta_4 range for the diff map
THETA1_MIN_DEG = -10.0
THETA1_MAX_DEG = 10.0
THETA4_MIN_DEG = -10.0
THETA4_MAX_DEG = 10.0

# Resolution of theta_1 and theta_4 grid in the diff map
N_THETA1 = 121
N_THETA4 = 121

# Slider ranges
THETA2_MIN_DEG = 45.0
THETA2_MAX_DEG = 65.0

THETA3_MIN_DEG = 90.0
THETA3_MAX_DEG = 130.0

# Initial slider values
INIT_THETA2_DEG = 55.0
INIT_THETA3_DEG = 110.0

# Resolution used when computing global terminal statistics
# Smaller step means more accurate but slower.
GLOBAL_THETA2_STEP_DEG = 1.0
GLOBAL_THETA3_STEP_DEG = 1.0

# Color range for diff map, in degrees.
# You can change this after seeing the printed global min/max.
COLOR_ABS_LIMIT_DEG = 10.0


# =========================
# Core geometry
# =========================

def compute_theta3_prime_deg(theta1_deg, theta2_deg, theta3_deg, theta4_deg):
    """
    Compute projected 2D angle theta3' from the corrected 3D model.

    Angles are in degrees.
    theta1_deg and theta4_deg may be scalars or numpy arrays.
    theta2_deg and theta3_deg are usually scalars.

    Convention:
    u = thigh direction from hip to knee.
    v = shank direction from knee to ankle.

    Corrected basis:
        a = (sin theta2 sin theta1,
             sin theta2 cos theta1,
            -cos theta2)

        b = (-cos theta1,
              sin theta1,
              0)

    Projection is along +x direction onto the yz plane.

    The projected angle is computed so that when theta1 = 0 and theta4 = 0,
    theta3' = theta3.
    """

    t1 = np.deg2rad(theta1_deg)
    t2 = np.deg2rad(theta2_deg)
    t3 = np.deg2rad(theta3_deg)
    t4 = np.deg2rad(theta4_deg)

    c1, s1 = np.cos(t1), np.sin(t1)
    c2, s2 = np.cos(t2), np.sin(t2)
    c3, s3 = np.cos(t3), np.sin(t3)
    c4, s4 = np.cos(t4), np.sin(t4)

    # Thigh direction u
    # u = (c2*s1, c2*c1, s2)
    u_y = c2 * c1
    u_z = s2

    # Corrected shank direction v
    v_y = c1 * (c3 * c2 + s3 * c4 * s2) + s1 * s3 * s4
    v_z = c3 * s2 - s3 * c4 * c2

    # 2D signed angle in yz plane.
    # det = u_y * v_z - u_z * v_y
    # With the corrected a,b, ideal case gives det = -sin(theta3).
    # Therefore use -det as atan2 numerator.
    det = u_y * v_z - u_z * v_y
    dot = u_y * v_y + u_z * v_z

    theta3_prime_rad = np.arctan2(-det, dot)
    theta3_prime_deg = np.rad2deg(theta3_prime_rad)

    return theta3_prime_deg


def compute_diff_map(theta2_deg, theta3_deg, theta1_grid_deg, theta4_grid_deg):
    """
    Compute diff = theta3' - theta3 over theta1/theta4 grid.
    """
    theta3_prime_deg = compute_theta3_prime_deg(
        theta1_grid_deg,
        theta2_deg,
        theta3_deg,
        theta4_grid_deg
    )

    diff_deg = theta3_prime_deg - theta3_deg
    return diff_deg


def summarize_diff(diff_deg):
    """
    Return max, min, and mean absolute diff.
    """
    diff_max = np.max(diff_deg)
    diff_min = np.min(diff_deg)
    diff_abs_mean = np.mean(np.abs(diff_deg))
    return diff_max, diff_min, diff_abs_mean


# =========================
# Prepare theta1-theta4 grid
# =========================

theta1_values = np.linspace(THETA1_MIN_DEG, THETA1_MAX_DEG, N_THETA1)
theta4_values = np.linspace(THETA4_MIN_DEG, THETA4_MAX_DEG, N_THETA4)

Theta1_grid, Theta4_grid = np.meshgrid(theta1_values, theta4_values)


# =========================
# Global terminal statistics
# =========================

def compute_global_statistics():
    theta2_all = np.arange(
        THETA2_MIN_DEG,
        THETA2_MAX_DEG + 0.5 * GLOBAL_THETA2_STEP_DEG,
        GLOBAL_THETA2_STEP_DEG
    )

    theta3_all = np.arange(
        THETA3_MIN_DEG,
        THETA3_MAX_DEG + 0.5 * GLOBAL_THETA3_STEP_DEG,
        GLOBAL_THETA3_STEP_DEG
    )

    global_max = -np.inf
    global_min = np.inf
    global_abs_sum = 0.0
    global_count = 0

    worst_max_case = None
    worst_min_case = None

    for theta2_deg in theta2_all:
        for theta3_deg in theta3_all:
            diff = compute_diff_map(
                theta2_deg,
                theta3_deg,
                Theta1_grid,
                Theta4_grid
            )

            local_max = np.max(diff)
            local_min = np.min(diff)

            if local_max > global_max:
                global_max = local_max
                worst_max_case = (theta2_deg, theta3_deg)

            if local_min < global_min:
                global_min = local_min
                worst_min_case = (theta2_deg, theta3_deg)

            global_abs_sum += np.sum(np.abs(diff))
            global_count += diff.size

    global_abs_mean = global_abs_sum / global_count

    print("\n========== Global statistics over sampled combinations ==========")
    print(f"theta2 range: {THETA2_MIN_DEG:.1f}° to {THETA2_MAX_DEG:.1f}°, "
          f"step = {GLOBAL_THETA2_STEP_DEG:.2f}°")
    print(f"theta3 range: {THETA3_MIN_DEG:.1f}° to {THETA3_MAX_DEG:.1f}°, "
          f"step = {GLOBAL_THETA3_STEP_DEG:.2f}°")
    print(f"theta1 range: {THETA1_MIN_DEG:.1f}° to {THETA1_MAX_DEG:.1f}°, "
          f"grid points = {N_THETA1}")
    print(f"theta4 range: {THETA4_MIN_DEG:.1f}° to {THETA4_MAX_DEG:.1f}°, "
          f"grid points = {N_THETA4}")
    print("---------------------------------------------------------------")
    print(f"Global max diff:       {global_max:.6f}° "
          f"at theta2={worst_max_case[0]:.2f}°, theta3={worst_max_case[1]:.2f}°")
    print(f"Global min diff:       {global_min:.6f}° "
          f"at theta2={worst_min_case[0]:.2f}°, theta3={worst_min_case[1]:.2f}°")
    print(f"Global mean |diff|:    {global_abs_mean:.6f}°")
    print("===============================================================\n")


# Run global statistics once at startup
compute_global_statistics()


# =========================
# Interactive plot
# =========================

fig = plt.figure(figsize=(15, 7))

# Leave space at bottom for sliders
plt.subplots_adjust(left=0.07, right=0.95, bottom=0.22, top=0.88, wspace=0.28)

ax_heatmap = fig.add_subplot(1, 2, 1)
ax_surface = fig.add_subplot(1, 2, 2, projection="3d")

# Initial diff map
diff_init = compute_diff_map(
    INIT_THETA2_DEG,
    INIT_THETA3_DEG,
    Theta1_grid,
    Theta4_grid
)

vmin = -COLOR_ABS_LIMIT_DEG
vmax = COLOR_ABS_LIMIT_DEG

im = ax_heatmap.imshow(
    diff_init,
    extent=[
        THETA1_MIN_DEG,
        THETA1_MAX_DEG,
        THETA4_MIN_DEG,
        THETA4_MAX_DEG
    ],
    origin="lower",
    aspect="auto",
    vmin=vmin,
    vmax=vmax,
    cmap="coolwarm"
)

cbar = fig.colorbar(im, ax=ax_heatmap)
cbar.set_label(r"$\theta_3' - \theta_3$ (deg)")

ax_heatmap.set_xlabel(r"$\theta_1$ (deg)")
ax_heatmap.set_ylabel(r"$\theta_4$ (deg)")
ax_heatmap.set_title("2D diff map")

# Add contour lines for readability
contour = ax_heatmap.contour(
    Theta1_grid,
    Theta4_grid,
    diff_init,
    levels=10,
    colors="black",
    linewidths=0.4,
    alpha=0.5
)

# 3D surface
surface = ax_surface.plot_surface(
    Theta1_grid,
    Theta4_grid,
    diff_init,
    cmap="coolwarm",
    vmin=vmin,
    vmax=vmax,
    linewidth=0,
    antialiased=True,
    alpha=0.95
)

ax_surface.set_xlabel(r"$\theta_1$ (deg)")
ax_surface.set_ylabel(r"$\theta_4$ (deg)")
ax_surface.set_zlabel(r"$\theta_3' - \theta_3$ (deg)")
ax_surface.set_title("3D diff surface")
ax_surface.set_zlim(vmin, vmax)

# Text summary in the figure
diff_max, diff_min, diff_abs_mean = summarize_diff(diff_init)
summary_text = fig.suptitle(
    f"theta2 = {INIT_THETA2_DEG:.2f}°, theta3 = {INIT_THETA3_DEG:.2f}° | "
    f"max diff = {diff_max:.4f}°, min diff = {diff_min:.4f}°, "
    f"mean |diff| = {diff_abs_mean:.4f}°",
    fontsize=12
)

# Sliders
ax_theta2 = plt.axes([0.15, 0.11, 0.72, 0.03])
ax_theta3 = plt.axes([0.15, 0.06, 0.72, 0.03])

slider_theta2 = Slider(
    ax=ax_theta2,
    label=r"$\theta_2$ (deg)",
    valmin=THETA2_MIN_DEG,
    valmax=THETA2_MAX_DEG,
    valinit=INIT_THETA2_DEG,
    valstep=0.1
)

slider_theta3 = Slider(
    ax=ax_theta3,
    label=r"$\theta_3$ (deg)",
    valmin=THETA3_MIN_DEG,
    valmax=THETA3_MAX_DEG,
    valinit=INIT_THETA3_DEG,
    valstep=0.1
)

def remove_contour(contour_set):
    """
    Safely remove a Matplotlib contour set.

    Different Matplotlib versions expose contour artists differently.
    Newer versions support contour_set.remove().
    Older versions may use contour_set.collections.
    """
    if contour_set is None:
        return

    # Newer Matplotlib versions
    if hasattr(contour_set, "remove"):
        try:
            contour_set.remove()
            return
        except Exception:
            pass

    # Older Matplotlib versions
    if hasattr(contour_set, "collections"):
        for artist in contour_set.collections:
            try:
                artist.remove()
            except Exception:
                pass

def update(_):
    global contour

    theta2_deg = slider_theta2.val
    theta3_deg = slider_theta3.val

    diff = compute_diff_map(
        theta2_deg,
        theta3_deg,
        Theta1_grid,
        Theta4_grid
    )

    # Update heatmap
    im.set_data(diff)

    # Remove old contour lines
    remove_contour(contour)

    contour = ax_heatmap.contour(
        Theta1_grid,
        Theta4_grid,
        diff,
        levels=10,
        colors="black",
        linewidths=0.4,
        alpha=0.5
    )

    # Update 3D surface by clearing and redrawing
    ax_surface.cla()
    ax_surface.plot_surface(
        Theta1_grid,
        Theta4_grid,
        diff,
        cmap="coolwarm",
        vmin=vmin,
        vmax=vmax,
        linewidth=0,
        antialiased=True,
        alpha=0.95
    )

    ax_surface.set_xlabel(r"$\theta_1$ (deg)")
    ax_surface.set_ylabel(r"$\theta_4$ (deg)")
    ax_surface.set_zlabel(r"$\theta_3' - \theta_3$ (deg)")
    ax_surface.set_title("3D diff surface")
    ax_surface.set_zlim(vmin, vmax)

    diff_max, diff_min, diff_abs_mean = summarize_diff(diff)

    summary_text.set_text(
        f"theta2 = {theta2_deg:.2f}°, theta3 = {theta3_deg:.2f}° | "
        f"max diff = {diff_max:.4f}°, min diff = {diff_min:.4f}°, "
        f"mean |diff| = {diff_abs_mean:.4f}°"
    )

    fig.canvas.draw_idle()


slider_theta2.on_changed(update)
slider_theta3.on_changed(update)

plt.show()