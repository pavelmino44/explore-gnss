import numpy as np
from solver import Solver

def solve_gnss(data: dict) -> dict:
    sol = Solver()
    result = sol.solve(data)
    return result