"""
Create PowerPoint-ready visualization of savings recommendations matrix
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import pandas as pd
import os

# Professional color scheme
COLORS = {
    '$1M': '#2E86AB',      # Deep blue
    '$500k': '#A23B72',    # Purple
    '$250k': '#F18F01',    # Orange
    'header': '#2C3E50',   # Dark gray
    'legend': '#E8F4F8'    # Light blue
}

def create_savings_matrix():
    """
    Create a clean, PowerPoint-ready matrix visualization
    """
    # Data structure
    data = {
        '$1M': {
            'Off-load Risk': ['ICHRA', 'Incentive move to exchange', 'Small group plan',
                             'Partnership with BAI (HCC removal)', 'Exclude specialty coverage'],
            'Improve purchasing (lower unit cost)': ['Reference Pricing'],
            'Shift costs (employes bear more)': [],
            'Reduce exposure (manage eligibility)': [],
            'Clinical/utilization management': []
        },
        '$500k': {
            'Off-load Risk': [],
            'Improve purchasing (lower unit cost)': ['HPNs'],
            'Shift costs (employes bear more)': [],
            'Reduce exposure (manage eligibility)': ['Dependent audit'],
            'Clinical/utilization management': ['Pharmacy risk management']
        },
        '$250k': {
            'Off-load Risk': [],
            'Improve purchasing (lower unit cost)': ['Variable copay plans'],
            'Shift costs (employes bear more)': ['Voluntary dental plan', 'Plan design changes'],
            'Reduce exposure (manage eligibility)': ['Spousal coverage exclusion'],
            'Clinical/utilization management': ['Pharmacy narrow networks']
        }
    }

    # Create figure
    fig, ax = plt.subplots(figsize=(16, 10))
    ax.set_xlim(0, 6)
    ax.set_ylim(0, 8)
    ax.axis('off')

    # Title
    ax.text(3, 7.5, 'Healthcare Savings Recommendations Matrix',
           ha='center', va='top', fontsize=22, fontweight='bold', color=COLORS['header'])

    # Column headers
    categories = [
        'Off-load Risk',
        'Improve Purchasing\n(Lower Unit Cost)',
        'Shift Costs\n(Employees Bear More)',
        'Reduce Exposure\n(Manage Eligibility)',
        'Clinical/Utilization\nManagement'
    ]

    col_width = 1.15
    start_x = 0.3
    header_y = 6.8

    for i, cat in enumerate(categories):
        x = start_x + (i * col_width)
        # Header background
        rect = FancyBboxPatch((x, header_y - 0.5), col_width - 0.05, 0.45,
                             boxstyle="round,pad=0.02",
                             facecolor=COLORS['header'],
                             edgecolor='white', linewidth=2)
        ax.add_patch(rect)
        # Header text
        ax.text(x + (col_width - 0.05)/2, header_y - 0.275,
               cat, ha='center', va='center',
               fontsize=9, fontweight='bold', color='white',
               wrap=True)

    # Row data
    row_heights = [2.0, 2.0, 2.0]
    impact_levels = ['$1M', '$500k', '$250k']
    start_y = 6.0

    for row_idx, (impact, height) in enumerate(zip(impact_levels, row_heights)):
        y = start_y - sum(row_heights[:row_idx])

        # Impact label
        label_rect = FancyBboxPatch((0.05, y - height + 0.1), 0.2, height - 0.2,
                                   boxstyle="round,pad=0.02",
                                   facecolor=COLORS[impact],
                                   edgecolor='white', linewidth=2)
        ax.add_patch(label_rect)
        ax.text(0.15, y - height/2, impact,
               ha='center', va='center',
               fontsize=14, fontweight='bold', color='white',
               rotation=0)

        # Category cells
        for col_idx, cat in enumerate(['Off-load Risk',
                                       'Improve purchasing (lower unit cost)',
                                       'Shift costs (employes bear more)',
                                       'Reduce exposure (manage eligibility)',
                                       'Clinical/utilization management']):
            x = start_x + (col_idx * col_width)

            # Cell background
            cell_rect = FancyBboxPatch((x, y - height + 0.1), col_width - 0.05, height - 0.2,
                                      boxstyle="round,pad=0.02",
                                      facecolor='white',
                                      edgecolor=COLORS[impact], linewidth=1.5,
                                      alpha=0.9)
            ax.add_patch(cell_rect)

            # Cell content
            items = data[impact][cat]
            if items:
                text_y = y - 0.3
                for item in items:
                    # Truncate long text
                    display_text = item if len(item) <= 25 else item[:22] + '...'
                    ax.text(x + 0.05, text_y, f'• {display_text}',
                           ha='left', va='top',
                           fontsize=7.5, color=COLORS['header'],
                           wrap=True)
                    text_y -= 0.3

    # Legend
    legend_y = 0.5
    ax.text(0.3, legend_y, 'Impact Level:', fontsize=10, fontweight='bold', color=COLORS['header'])

    legend_items = [
        ('$1M+', COLORS['$1M']),
        ('$500k', COLORS['$500k']),
        ('$250k', COLORS['$250k'])
    ]

    legend_x = 1.2
    for label, color in legend_items:
        rect = FancyBboxPatch((legend_x, legend_y - 0.15), 0.3, 0.25,
                             boxstyle="round,pad=0.02",
                             facecolor=color, edgecolor='white', linewidth=1.5)
        ax.add_patch(rect)
        ax.text(legend_x + 0.15, legend_y - 0.025, label,
               ha='center', va='center',
               fontsize=9, fontweight='bold', color='white')
        legend_x += 0.4

    # Footer note
    ax.text(3, 0.1, 'Color-coded by savings potential  |  Organized by strategic approach',
           ha='center', va='bottom',
           fontsize=9, style='italic', color='gray')

    plt.tight_layout()

    # Save as high-res PNG for PowerPoint
    os.makedirs('.tmp/charts', exist_ok=True)
    output_path = '.tmp/charts/savings_recommendations_matrix.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight',
               facecolor='white', edgecolor='none')
    print(f"\n✓ PowerPoint-ready chart saved to: {output_path}")
    print(f"  Resolution: 300 DPI (high quality for presentations)")
    print(f"  Format: PNG with white background")
    print(f"  Ready to insert into PowerPoint!")

    plt.close()

    return output_path

if __name__ == "__main__":
    create_savings_matrix()
