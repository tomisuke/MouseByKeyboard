import time
import win32gui
import comtypes
import uiautomation as auto

# Find an active or Explorer window
hwnd = win32gui.GetForegroundWindow()
print(f"Target HWND: {hwnd}, Class: {win32gui.GetClassName(hwnd)}")

CLICKABLE_TYPE_IDS = frozenset({
    50000, 50002, 50003, 50004, 50005, 50007, 50011, 50013, 50019, 50024, 50029, 50031
})

# 1. Base implementation (current logic)
def scan_tree_base(ctrl, results, depth=0):
    if depth > 30:
        return
    try:
        if ctrl.ControlType in CLICKABLE_TYPE_IDS:
            r = ctrl.BoundingRectangle
            if r.width() > 0 and r.height() > 0:
                results.append((r, ctrl))
                return
        for child in ctrl.GetChildren():
            scan_tree_base(child, results, depth + 1)
    except Exception:
        pass

# 2. Optimized implementation with CacheRequest
def scan_tree_cached(ctrl, results, depth=0):
    if depth > 30:
        return
    try:
        # Properties should be cached already if we fetched children with a cache request active.
        # When using CacheRequest, we access properties via CachedControlType, CachedBoundingRectangle etc.
        # Let's see if uiautomation supports cached properties.
        # Usually, they are prefixed with "Cached" or accessed normally if uiautomation maps them.
        # Let's print properties to see what we get when cached.
        c_type = ctrl.CachedControlType
        r = ctrl.CachedBoundingRectangle
        if c_type in CLICKABLE_TYPE_IDS:
            if r.width() > 0 and r.height() > 0:
                results.append((r, ctrl))
                return
        # Get children with cache request
        # In uiautomation: ctrl.GetChildren() will use the active CacheRequest if we handle it.
        for child in ctrl.GetChildren():
            scan_tree_cached(child, results, depth + 1)
    except Exception as e:
        # If CachedControlType is not supported directly, we will see the error.
        pass

# Let's test basic speed first
comtypes.CoInitialize()
try:
    ctrl = auto.ControlFromHandle(hwnd)
    
    # Test Base
    t0 = time.time()
    results_base = []
    scan_tree_base(ctrl, results_base)
    print(f"Base Walk: found {len(results_base)} elements in {(time.time()-t0)*1000:.1f}ms")
    
    # Test CacheRequest
    # uiautomation syntax: 
    # cache = auto.CacheRequest()
    # cache.AddProperty(auto.PropertyId.ControlTypePropertyId)
    # cache.AddProperty(auto.PropertyId.BoundingRectanglePropertyId)
    # With cache:
    # We can activate cache by entering a context:
    # with cache:
    #     ...
    # Let's test if cache is available
    try:
        cache = auto.CacheRequest()
        cache.AddProperty(auto.ControlTypePropertyId)
        cache.AddProperty(auto.BoundingRectanglePropertyId)
        
        t0 = time.time()
        results_cache = []
        with cache:
            # Re-fetch control or children with cache
            # The root control itself might not have cached properties unless we fetched it with cache,
            # but children fetched inside "with cache" should have them.
            # In uiautomation, we can use ctrl.GetChildren() inside "with cache".
            # Let's test.
            # To be safe, let's wrap the walk inside "with cache"
            # Note: inside scan_tree_cached, we use ctrl.CachedControlType and ctrl.CachedBoundingRectangle.
            # Let's check if they exist on the root first.
            try:
                # Root won't have cached properties if fetched without cache, but let's see.
                scan_tree_cached(ctrl, results_cache)
            except Exception as e:
                print("Cache walk failed:", e)
        print(f"Cached Walk: found {len(results_cache)} elements in {(time.time()-t0)*1000:.1f}ms")
    except Exception as e:
        print("CacheRequest setup failed:", e)

finally:
    comtypes.CoUninitialize()
