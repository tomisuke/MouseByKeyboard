import uiautomation as auto
print("Attributes in uiautomation:")
attrs = dir(auto)
for attr in attrs:
    if 'cache' in attr.lower() or 'request' in attr.lower() or 'walk' in attr.lower():
        print("  ", attr)
