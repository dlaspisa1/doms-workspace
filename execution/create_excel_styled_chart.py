"""
Create PowerPoint-ready chart that maintains Excel structure but beautifies it
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Rectangle
import pandas as pd
import os

# Professional color scheme
COLORS = {
    'range_label': '#4A5568',  # Dark gray for range labels
    'header': '#2D3748',       # Darker gray for headers
    'cell_fill_1': '#E6F3FF',  # Light blue
    'cell_fill_2': '#FFF5E6',  # Light orange
    'border': '#CBD5E0',       # Light gray border
    'text': '#2D3748'          # Dark text
}

def create_excel_styled_matrix():
    """
    Recreate the Excel structure with PowerPoint-ready styling
    """
    # Read the original Excel data
    df = pd.read_excel('.tmp/email_attachments/Savings overview01.xlsx', sheet_name=0)

    # Create figure with exact proportions
    fig, ax = plt.subplots(figsize=(18, 12))
    ax.set_xlim(0, 7)
    ax.set_ylim(0, 16)
    ax.axis('off')

    # Column headers (matching Excel columns C through G)
    headers = [
        'Off-load Risk',
        'Improve purchasing\n(lower unit cost)',
        'Shift costs\n(employees bear more)',
        'Reduce exposure\n(manage eligibility)',
        'Clinical/utilization\nmanagement'
    ]

    col_width = 1.3
    start_x = 1.2
    header_y = 15

    # Draw column headers
    for i, header in enumerate(headers):
        x = start_x + (i * col_width)
        # Header cell
        rect = Rectangle((x, header_y - 0.6), col_width - 0.05, 0.6,
                         facecolor=COLORS['header'],
                         edgecolor='white', linewidth=2)
        ax.add_patch(rect)
        # Header text
        ax.text(x + (col_width - 0.05)/2, header_y - 0.3,
               header, ha='center', va='center',
               fontsize=10, fontweight='bold', color='white',
               multialignment='center')

    # Data rows - maintaining exact Excel structure
    # Row 1: $1M range
    y_pos = 14.2

    # $1M label
    ax.text(0.6, y_pos - 2.5, '$1M', ha='center', va='center',
           fontsize=16, fontweight='bold', color=COLORS['range_label'],
           bbox=dict(boxstyle='round,pad=0.5', facecolor='#E8F4F8',
                    edgecolor=COLORS['range_label'], linewidth=2))

    # $1M row items
    row_data_1m = [
        ['ICHRA', 'Incentive move to exchange', 'Small group plan',
         'Partnership with BAI (HCC removal)', 'Exclude specialty coverage'],
        ['Reference Pricing'],
        [],
        [],
        []
    ]

    for col_idx, items in enumerate(row_data_1m):
        x = start_x + (col_idx * col_width)
        # Cell background
        rect = Rectangle((x, y_pos - 5.0), col_width - 0.05, 5.0,
                         facecolor='white',
                         edgecolor=COLORS['border'], linewidth=1.5)
        ax.add_patch(rect)

        # Cell items
        if items:
            item_y = y_pos - 0.5
            for item in items:
                ax.text(x + 0.1, item_y, f'• {item}',
                       ha='left', va='top',
                       fontsize=9, color=COLORS['text'],
                       wrap=True, multialignment='left')
                item_y -= 0.9

    # Row 2: $500k range
    y_pos = 9.0

    # $500k label
    ax.text(0.6, y_pos - 1.5, '$500k', ha='center', va='center',
           fontsize=16, fontweight='bold', color=COLORS['range_label'],
           bbox=dict(boxstyle='round,pad=0.5', facecolor='#F8E8F4',
                    edgecolor=COLORS['range_label'], linewidth=2))

    # $500k row items
    row_data_500k = [
        [],
        ['HPNs'],
        [],
        ['Dependent audit'],
        ['Pharmacy risk management']
    ]

    for col_idx, items in enumerate(row_data_500k):
        x = start_x + (col_idx * col_width)
        # Cell background
        rect = Rectangle((x, y_pos - 3.0), col_width - 0.05, 3.0,
                         facecolor='white',
                         edgecolor=COLORS['border'], linewidth=1.5)
        ax.add_patch(rect)

        # Cell items
        if items:
            item_y = y_pos - 0.5
            for item in items:
                ax.text(x + 0.1, item_y, f'• {item}',
                       ha='left', va='top',
                       fontsize=9, color=COLORS['text'],
                       wrap=True, multialignment='left')
                item_y -= 0.9

    # Row 3: $250k range
    y_pos = 5.8

    # $250k label
    ax.text(0.6, y_pos - 1.5, '$250k', ha='center', va='center',
           fontsize=16, fontweight='bold', color=COLORS['range_label'],
           bbox=dict(boxstyle='round,pad=0.5', facecolor='#FFF5E6',
                    edgecolor=COLORS['range_label'], linewidth=2))

    # $250k row items
    row_data_250k = [
        [],
        ['Variable copay plans'],
        ['Voluntary dental plan', 'Plan design changes'],
        ['Spousal coverage exclusion'],
        ['Pharmacy narrow networks']
    ]

    for col_idx, items in enumerate(row_data_250k):
        x = start_x + (col_idx * col_width)
        # Cell background
        rect = Rectangle((x, y_pos - 3.0), col_width - 0.05, 3.0,
                         facecolor='white',
                         edgecolor=COLORS['border'], linewidth=1.5)
        ax.add_patch(rect)

        # Cell items
        if items:
            item_y = y_pos - 0.5
            for item in items:
                ax.text(x + 0.1, item_y, f'• {item}',
                       ha='left', va='top',
                       fontsize=9, color=COLORS['text'],
                       wrap=True, multialignment='left')
                item_y -= 0.9

    # Legend section (from Excel)
    legend_y = 2.0

    # "Color code:" label
    ax.text(start_x, legend_y, 'Color code:',
           ha='left', va='center',
           fontsize=10, fontweight='bold', color=COLORS['text'])

    # Legend items
    ax.text(start_x + 1.3, legend_y, 'Target specific risk',
           ha='left', va='center',
           fontsize=9, color=COLORS['text'],
           bbox=dict(boxstyle='round,pad=0.3', facecolor='#E8F4F8',
                    edgecolor=COLORS['border'], linewidth=1))

    ax.text(start_x, legend_y - 0.5, 'Overall plan management',
           ha='left', va='center',
           fontsize=9, color=COLORS['text'],
           bbox=dict(boxstyle='round,pad=0.3', facecolor='#FFF5E6',
                    edgecolor=COLORS['border'], linewidth=1))

    # Title
    ax.text(3.9, 15.8, 'Recommendations',
           ha='center', va='bottom',
           fontsize=20, fontweight='bold', color=COLORS['header'])

    plt.tight_layout()

    # Save as high-res PNG for PowerPoint
    os.makedirs('.tmp/charts', exist_ok=True)
    output_path = '.tmp/charts/savings_recommendations_ppt.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight',
               facecolor='white', edgecolor='none')
    print(f"\n✓ PowerPoint-ready chart saved to: {output_path}")
    print(f"  Maintains original Excel structure")
    print(f"  Resolution: 300 DPI")
    print(f"  Ready to insert into PowerPoint!")

    plt.close()

    return output_path

if __name__ == "__main__":
    create_excel_styled_matrix()
