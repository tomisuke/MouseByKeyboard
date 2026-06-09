import uiautomation as auto

print("All attributes containing 'Walker' or 'View' in uiautomation:")
for attr in dir(auto):
    if 'walker' in attr.lower() or 'view' in attr.lower():
        print(f"  {attr}")
