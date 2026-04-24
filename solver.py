import random as rd
import numpy as np

class Solver:
    def __init__(self):
        self.beacons = None
        self.active_beacons = None
        self.receiver = None
        self.measurement_error = None
        self.noise_std = None


    def load_data(self, data):
        self.beacons = data['beacons']
        self.active_beacons = [{'x': float(b['x']), 'y': float(b['y'])} for b in data['beacons'] if b['enabled'] == True]
        self.receiver = data['receiver']
        self.measurement_error = data['measurement_error']
        self.noise_std = data['noise_std']

    def generate_pseudorange(self):
        p = []
        for b in self.active_beacons:
            r = np.sqrt((float(self.receiver['x']) - b['x'])**2 + (float(self.receiver['y']) - b['y'])**2) + float(self.measurement_error) + rd.gauss(0,self.noise_std)
            p.append(r)
        return p

    def least_squares_method(self):
        p = self.generate_pseudorange()
        X_0 = np.array([0., 0., 0.]).reshape(-1, 1)
        X_history = [X_0.copy()]

        for _ in range(100):
            H = []
            D = []
            K = []
            for b in self.active_beacons:
                h = []
                d = np.sqrt((X_0[0][0] - b['x'])**2 + (X_0[1][0] - b['y'])**2)
                D.append(d)
                h.append((X_0[0][0] - b['x']) / d)
                h.append((X_0[1][0] - b['y']) / d)
                h.append(1)
                H.append(h)

            Y = np.array([p[k] - D[k] - X_0[2][0] for k in range(len(p))]).reshape(-1, 1)
            H = np.array(H)
            dX = np.linalg.inv(H.T @ H) @ H.T @ Y
            X_0 += dX
            X_history.append(X_0.copy())

            kovar = self.noise_std**2 * np.linalg.inv(H.T @ H)
            K.append(kovar[0:2,0:2])
            if np.abs(dX.sum()) < 1e-10:
                break
        return X_history, K


    def solve(self, data):
        self.load_data(data)
        try:
            X_history, K = self.least_squares_method()
            x = X_history[-1][0][0]
            y = X_history[-1][1][0]
            error = np.sqrt( (float(self.receiver['x']) - x) ** 2 + (float(self.receiver['y']) - y) ** 2 )
            it = [{'x': float(his[0][0]), 'y': float(his[1][0])} for his in X_history ]
            kov = K[-1]

            result = {
                'estimated': {'x': float(x), 'y': float(y)},
                'error': error,
                'covariance': kov,
                'used_beacons': self.active_beacons,
                'iterations': it,
                'CalculationError': False
            }

        except Exception as e:
            result = {
                'used_beacons': self.active_beacons,
                'CalculationError': True
            }

        return result

if __name__ == '__main__':
    data = {
        'beacons': [
            {'x': 0 , 'y':  100, 'enabled': True},
            {'x':  0, 'y':  500, 'enabled': True},
            {'x': 0, 'y': -700, 'enabled': True},
            {'x':  0, 'y': -600, 'enabled': True},
            {'x':  0 , 'y':  800, 'enabled': True}
        ],
        'receiver':{
            'x': 20,
            'y': -200
        },
        'noise_std': 1,
        'measurement_error': -10
    }

    solver = Solver()

    result = solver.solve(data)
    for x in result:
        print(result[x])
