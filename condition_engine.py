import os
import re
import json
import time
import asyncio
import api

COOLDOWN_FILE = "/tmp/pi_solar_cooldowns.json"

def parse_duration(duration_str):
    if not duration_str:
        return 0
    duration_str = str(duration_str).strip().lower()
    match = re.match(r'^(\d+)([smhd])$', duration_str)
    if not match:
        try:
            return int(duration_str)
        except:
            return 0
    value, unit = match.groups()
    value = int(value)
    if unit == 's': return value
    if unit == 'm': return value * 60
    if unit == 'h': return value * 3600
    if unit == 'd': return value * 86400
    return 0

class ConditionEngine:
    def __init__(self):
        self.cooldowns = self.load_cooldowns()
        self._config_cache = {} # filename -> {'mtime': ..., 'config': ...}

    def load_cooldowns(self):
        if os.path.exists(COOLDOWN_FILE):
            try:
                with open(COOLDOWN_FILE, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_cooldowns(self):
        try:
            # Ensure directory exists (though /tmp usually does)
            os.makedirs(os.path.dirname(COOLDOWN_FILE), exist_ok=True)
            with open(COOLDOWN_FILE, 'w') as f:
                json.dump(self.cooldowns, f)
        except Exception as e:
            print(f"Error saving cooldowns: {e}")

    def purge_old_cooldowns(self):
        now = time.time()
        # Keep only entries from the last 48 hours
        before_count = len(self.cooldowns)
        self.cooldowns = {k: v for k, v in self.cooldowns.items() if now - v < 48 * 3600}
        if len(self.cooldowns) != before_count:
            print(f"Purged {before_count - len(self.cooldowns)} old cooldown entries.")
            self.save_cooldowns()

    async def evaluate_path(self, path, current_data=None):
        """
        Evaluates an internal API path and returns the value.
        Example paths:
        /api/data/pv_voltage/last
        /api/data/pv_voltage/stats/avg?start=1h
        """
        try:
            if '?' in path:
                base_path, query_str = path.split('?', 1)
                # Simple query param parser
                query_params = dict(re.findall(r'([^=&]+)=([^&]*)', query_str))
            else:
                base_path = path
                query_params = {}

            parts = base_path.strip('/').split('/')
            # Expected parts: ['api', 'data', '{key}', 'last']
            # or ['api', 'data', '{key}', 'stats', '{stat_key}']

            if len(parts) < 4:
                return None

            key = parts[2]
            metric = parts[3]

            if metric == 'last':
                # Optimization: if current_data is provided, use it instead of querying DB
                if current_data and key in current_data:
                    return current_data[key]
                res = await api.get_data_last(key)
                return res.get('value')
            elif metric == 'stats' and len(parts) >= 5:
                stat_key = parts[4]
                res = await api.get_data_stats(
                    key,
                    start=query_params.get('start'),
                    end=query_params.get('end'),
                    gt=float(query_params.get('gt')) if 'gt' in query_params else None,
                    lt=float(query_params.get('lt')) if 'lt' in query_params else None,
                    eq=float(query_params.get('eq')) if 'eq' in query_params else None
                )
                return res.get(stat_key)
        except Exception as e:
            print(f"Error evaluating path {path}: {e}")
        return None

    async def process_expression(self, expr, current_data=None):
        """
        Substitutes API paths in an expression with their values and evaluates it.
        """
        # Find all /api/data/... occurrences.
        # They might be inside quotes or unquoted.
        path_pattern = r'/api/data/[^\s\'\)]+'
        paths = re.findall(path_pattern, expr)

        if not paths:
            # If no paths, just try to eval it (might be a constant expression)
            pass

        # Sort paths by length descending to avoid partial replacement issues
        for path in sorted(set(paths), key=len, reverse=True):
            if hasattr(self, '_current_eval_cache') and path in self._current_eval_cache:
                val = self._current_eval_cache[path]
            else:
                val = await self.evaluate_path(path, current_data=current_data)
                if hasattr(self, '_current_eval_cache'):
                    self._current_eval_cache[path] = val

            if val is None:
                raise ValueError(f"Data not available for {path}")

            # Replace path in expr.
            # We handle quoted paths by replacing them including the quotes.
            # Python's eval will then see the numeric value.
            expr = expr.replace(f"'{path}'", str(val))
            expr = expr.replace(f'"{path}"', str(val))
            expr = expr.replace(path, str(val))

        # restricted eval
        safe_dict = {
            "round": round,
            "abs": abs,
            "min": min,
            "max": max,
            "int": int,
            "float": float,
            "bool": bool
        }
        # We allow some basic builtins for math and type conversion
        return eval(expr, {"__builtins__": None}, safe_dict)

    def parse_file(self, filepath):
        with open(filepath, 'r') as f:
            lines = f.readlines()

        config = {'or': [], 'and': [], 'action': None, 'cooldown': '0s'}
        current_section = None

        # Helper to split multiple conditions on one line
        def split_conditions(text):
            return [p for p in re.split(r'\s+(?=[\'"]?/api/data/)', text) if p.strip()]

        for line in lines:
            line = line.strip()
            if not line: continue

            if line.startswith('[conditions]'):
                current_section = 'conditions'
                continue

            if line.startswith('[or]'):
                current_section = 'or'
                content = line[len('[or]'):].strip()
                if content:
                    config['or'].extend(split_conditions(content))
                continue
            elif line.startswith('[and]'):
                current_section = 'and'
                content = line[len('[and]'):].strip()
                if content:
                    config['and'].extend(split_conditions(content))
                continue
            elif line.startswith('[action]'):
                current_section = 'action'
                content = line[len('[action]'):].strip()
                if content:
                    config['action'] = content
                continue
            elif line.startswith('[cooldown]'):
                current_section = 'cooldown'
                content = line[len('[cooldown]'):].strip()
                if content:
                    config['cooldown'] = content
                continue

            # Content lines for the current section
            if current_section == 'or':
                config['or'].extend(split_conditions(line))
            elif current_section == 'and':
                config['and'].extend(split_conditions(line))
            elif current_section == 'action':
                # For action, we take the whole line
                if config['action']:
                    config['action'] += " " + line
                else:
                    config['action'] = line
            elif current_section == 'cooldown':
                config['cooldown'] = line

        return config

    async def process_conditions(self, current_data=None):
        cond_dir = "conditions"
        if not os.path.exists(cond_dir):
            return

        # Optimization: Use a local cache for API evaluations within this single call
        # to avoid redundant calls to api.py functions for the same data
        self._current_eval_cache = {}

        try:
            for filename in os.listdir(cond_dir):
                if filename.endswith(".cond"):
                    filepath = os.path.join(cond_dir, filename)
                    try:
                        mtime = os.path.getmtime(filepath)
                        cached = self._config_cache.get(filename)

                        if cached and cached['mtime'] == mtime:
                            config = cached['config']
                        else:
                            config = self.parse_file(filepath)
                            self._config_cache[filename] = {
                                'mtime': mtime,
                                'config': config
                            }

                        if not config['action']:
                            continue

                        now = time.time()
                        last_exec = self.cooldowns.get(filename, 0)
                        cooldown_sec = parse_duration(config['cooldown'])

                        if now - last_exec < cooldown_sec:
                            continue

                        or_passed = True
                        if config['or']:
                            or_passed = False
                            for expr in config['or']:
                                try:
                                    if await self.process_expression(expr, current_data=current_data):
                                        or_passed = True
                                        break
                                except Exception as e:
                                    # print(f"OR Condition error in {filename}: {e}")
                                    pass

                        and_passed = True
                        if config['and']:
                            for expr in config['and']:
                                try:
                                    if not await self.process_expression(expr, current_data=current_data):
                                        and_passed = False
                                        break
                                except Exception as e:
                                    # print(f"AND Condition error in {filename}: {e}")
                                    and_passed = False
                                    break

                        if or_passed and and_passed:
                            print(f"Condition MET for {filename}: {config['action']}")
                            # Execute action asynchronously
                            try:
                                await asyncio.create_subprocess_shell(config['action'])
                            except Exception as e:
                                print(f"Failed to execute action for {filename}: {e}")

                            self.cooldowns[filename] = now
                            self.save_cooldowns()

                    except Exception as e:
                        print(f"Error processing condition file {filename}: {e}")
        finally:
            del self._current_eval_cache

# Global instance for easy use
engine = ConditionEngine()
