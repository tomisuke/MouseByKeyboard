import uiautomation as auto
import inspect

print("WalkControl signature:")
try:
    print(inspect.signature(auto.WalkControl))
except Exception as e:
    print(e)
print("WalkControl doc:")
print(auto.WalkControl.__doc__)

print("\nWalkTree signature:")
try:
    print(inspect.signature(auto.WalkTree))
except Exception as e:
    print(e)
print("WalkTree doc:")
print(auto.WalkTree.__doc__)
