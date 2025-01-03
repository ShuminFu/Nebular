# path/filename: coffee_distribution_pulp.py
"""
Official example of using pulp by calling LLMs
"""
import pulp
import time

# 定义数据
suppliers = ['supplier1', 'supplier2', 'supplier3']
roasteries = ['roastery1', 'roastery2']
cafes = ['cafe1', 'cafe2', 'cafe3']

capacity_in_supplier = {'supplier1': 150, 'supplier2': 50, 'supplier3': 100}
shipping_cost_from_supplier_to_roastery = {
    ('supplier1', 'roastery1'): 5,
    ('supplier1', 'roastery2'): 4,
    ('supplier2', 'roastery1'): 6,
    ('supplier2', 'roastery2'): 3,
    ('supplier3', 'roastery1'): 2,
    ('supplier3', 'roastery2'): 7
}
roasting_cost_light = {'roastery1': 3, 'roastery2': 5}
roasting_cost_dark = {'roastery1': 5, 'roastery2': 6}
shipping_cost_from_roastery_to_cafe = {
    ('roastery1', 'cafe1'): 5,
    ('roastery1', 'cafe2'): 3,
    ('roastery1', 'cafe3'): 6,
    ('roastery2', 'cafe1'): 4,
    ('roastery2', 'cafe2'): 5,
    ('roastery2', 'cafe3'): 2
}
light_coffee_needed_for_cafe = {'cafe1': 20, 'cafe2': 30, 'cafe3': 40}
dark_coffee_needed_for_cafe = {'cafe1': 20, 'cafe2': 20, 'cafe3': 100}

# 创建模型
model = pulp.LpProblem("Coffee_Distribution", pulp.LpMinimize)

# 创建变量
x = pulp.LpVariable.dicts("shipment_supplier_roastery", shipping_cost_from_supplier_to_roastery.keys(), lowBound=0, cat='Integer')
y_light = pulp.LpVariable.dicts("shipment_roastery_cafe_light", shipping_cost_from_roastery_to_cafe.keys(), lowBound=0, cat='Integer')
y_dark = pulp.LpVariable.dicts("shipment_roastery_cafe_dark", shipping_cost_from_roastery_to_cafe.keys(), lowBound=0, cat='Integer')

# 目标函数
model += (
    pulp.lpSum([x[s, r] * shipping_cost_from_supplier_to_roastery[(s, r)] for s, r in shipping_cost_from_supplier_to_roastery]) +
    pulp.lpSum([y_light[r, c] * (roasting_cost_light[r] + shipping_cost_from_roastery_to_cafe[(r, c)]) for r, c in shipping_cost_from_roastery_to_cafe]) +
    pulp.lpSum([y_dark[r, c] * (roasting_cost_dark[r] + shipping_cost_from_roastery_to_cafe[(r, c)]) for r, c in shipping_cost_from_roastery_to_cafe])
)

# 约束条件
# 供应限制
for s in suppliers:
    model += pulp.lpSum([x[s, r] for r in roasteries if (s, r) in x]) <= capacity_in_supplier[s], f"Supply_limit_{s}"

# 需求限制
for c in cafes:
    model += pulp.lpSum([y_light[r, c] for r in roasteries if (r, c) in y_light]) >= light_coffee_needed_for_cafe[c], f"Light_demand_{c}"
    model += pulp.lpSum([y_dark[r, c] for r in roasteries if (r, c) in y_dark]) >= dark_coffee_needed_for_cafe[c], f"Dark_demand_{c}"

# 解决模型
model.solve()

# 输出结果
print(time.ctime())
if pulp.LpStatus[model.status] == 'Optimal':
    print(f'Optimal cost: {pulp.value(model.objective)}')
else:
    print("Not solved to optimality. Optimization status:", pulp.LpStatus[model.status])
