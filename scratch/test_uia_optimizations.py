import time
import win32gui
import comtypes
import uiautomation as auto

CLICKABLE_TYPE_IDS = frozenset({
    50000, 50002, 50003, 50004, 50005, 50007, 50011, 50013, 50019, 50024, 50029, 50031
})

# Limit total scanned count to avoid hanging the test
MAX_SCANNED = 500

# 1. Base Implementation
def walk_base(ctrl, results, stats, depth=0):
    if depth > 35 or stats['count'] >= MAX_SCANNED:
        return
    stats['count'] += 1
    try:
        if ctrl.ControlType in CLICKABLE_TYPE_IDS:
            r = ctrl.BoundingRectangle
            if r.width() > 0 and r.height() > 0:
                results.append((r, ctrl))
                return # Pruning
        for child in ctrl.GetChildren():
            walk_base(child, results, stats, depth + 1)
    except Exception:
        pass

# 2. Opt 1: Depth limit = 15
def walk_opt1_depth(ctrl, results, stats, depth=0):
    if depth > 15 or stats['count'] >= MAX_SCANNED:
        return
    stats['count'] += 1
    try:
        if ctrl.ControlType in CLICKABLE_TYPE_IDS:
            r = ctrl.BoundingRectangle
            if r.width() > 0 and r.height() > 0:
                results.append((r, ctrl))
                return # Pruning
        for child in ctrl.GetChildren():
            walk_opt1_depth(child, results, stats, depth + 1)
    except Exception:
        pass

# 3. Opt 2: Depth limit + Offscreen container pruning
def walk_opt2_pruning(ctrl, results, stats, depth=0):
    if depth > 15 or stats['count'] >= MAX_SCANNED:
        return
    stats['count'] += 1
    try:
        r = ctrl.BoundingRectangle
        if r.width() <= 0 or r.height() <= 0:
            return # Skip scanning children of zero-size or collapsed containers
            
        if ctrl.ControlType in CLICKABLE_TYPE_IDS:
            results.append((r, ctrl))
            return # Pruning
            
        for child in ctrl.GetChildren():
            walk_opt2_pruning(child, results, stats, depth + 1)
    except Exception:
        pass

# 4. Opt 3: Sibling iteration + Depth limit + Size pruning
def walk_opt3_sibling(ctrl, results, stats, depth=0):
    if depth > 15 or stats['count'] >= MAX_SCANNED:
        return
    stats['count'] += 1
    try:
        r = ctrl.BoundingRectangle
        if r.width() <= 0 or r.height() <= 0:
            return # Skip
            
        if ctrl.ControlType in CLICKABLE_TYPE_IDS:
            results.append((r, ctrl))
            return # Pruning
            
        child = ctrl.GetFirstChildControl()
        while child:
            walk_opt3_sibling(child, results, stats, depth + 1)
            child = child.GetNextSiblingControl()
    except Exception:
        pass

comtypes.CoInitialize()
try:
    # Get the root desktop control
    ctrl = auto.GetRootControl()
    print("Desktop root control obtained. Running benchmarks...")
    
    # Test Base
    t0 = time.time()
    res_base = []
    stats_base = {'count': 0}
    walk_base(ctrl, res_base, stats_base)
    t_base = (time.time()-t0)*1000
    print(f"Base: found {len(res_base)} elements, visited {stats_base['count']} nodes in {t_base:.1f}ms")
    
    # Test Opt1 (Depth=15)
    t0 = time.time()
    res_opt1 = []
    stats_opt1 = {'count': 0}
    walk_opt1_depth(ctrl, res_opt1, stats_opt1)
    t_opt1 = (time.time()-t0)*1000
    print(f"Opt1 (Depth=15): found {len(res_opt1)} elements, visited {stats_opt1['count']} nodes in {t_opt1:.1f}ms")
    
    # Test Opt2 (Depth=15 + Size Pruning)
    t0 = time.time()
    res_opt2 = []
    stats_opt2 = {'count': 0}
    walk_opt2_pruning(ctrl, res_opt2, stats_opt2)
    t_opt2 = (time.time()-t0)*1000
    print(f"Opt2 (Size Pruning): found {len(res_opt2)} elements, visited {stats_opt2['count']} nodes in {t_opt2:.1f}ms")
    
    # Test Opt3 (Sibling iteration)
    t0 = time.time()
    res_opt3 = []
    stats_opt3 = {'count': 0}
    walk_opt3_sibling(ctrl, res_opt3, stats_opt3)
    t_opt3 = (time.time()-t0)*1000
    print(f"Opt3 (Sibling): found {len(res_opt3)} elements, visited {stats_opt3['count']} nodes in {t_opt3:.1f}ms")
    
finally:
    comtypes.CoUninitialize()
