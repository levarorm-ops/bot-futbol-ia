import numpy as np
import math

class NoticiasLiveScraper:
    """
    Simula el módulo 24/7 que rastrea noticias de última hora, 
    alineaciones confirmadas y eventos climáticos.
    """
    @staticmethod
    def obtener_impacto_noticias_live(equipo_local, equipo_visitante):
        """
        Calcula un multiplicador de impacto basado en noticias recientes:
        - Bajas/Lesiones clave (-10% a -20% en xG)
        - Noticias de vestuario o rotación de nómina
        """
        # En el entorno real, esto hace requests a APIs/RSS de noticias
        impacto_local = 1.0
        impacto_visitante = 1.0
        noticias_detectadas = []

        # Ejemplo de detección autónoma 24/7:
        # Si detecta que el delantero estrella del local se lesionó en el calentamiento:
        # impacto_local -= 0.15
        # noticias_detectadas.append("ALERTA 24/7: Lesión de última hora en el equipo local (-15% xG)")

        return impacto_local, impacto_visitante, noticias_detectadas


class BotGiga24Siete:
    def __init__(self, bankroll_cop=1000000, num_simulaciones=100000):
        self.bankroll = bankroll_cop
        self.num_sim = num_simulaciones

    def simular_con_noticias_247(self, p):
        # 1. Scraping e ingesta de noticias en vivo
        mod_noticias_loc, mod_noticias_vis, noticias = NoticiasLiveScraper.obtener_impacto_noticias_live(
            p['local'], p['visitante']
        )

        # 2. Ajustes contextuales (Hinchada, Aforo, Estadio)
        mod_contexto_loc = 1.0
        if p['aforo_pct'] >= 85 and p['crece_con_hinchada']:
            mod_contexto_loc += 0.12
        elif p['aforo_pct'] <= 30:
            mod_contexto_loc -= 0.08

        # xG Final Afectado por Noticias + Contexto
        xg_loc_final = p['xg_loc_base'] * mod_contexto_loc * mod_noticias_loc
        xg_vis_final = p['xg_vis_base'] * mod_noticias_vis

        # 3. Executar 100,000 Simulaciones de Montecarlo
        goles_loc = np.random.poisson(xg_loc_final, self.num_sim)
        goles_vis = np.random.poisson(xg_vis_final, self.num_sim)
        tarjetas_sim = np.random.poisson(p['promedio_tarjetas_ref'], self.num_sim)

        p_1 = np.sum(goles_loc > goles_vis) / self.num_sim
        p_X = np.sum(goles_loc == goles_vis) / self.num_sim
        p_2 = np.sum(goles_loc < goles_vis) / self.num_sim

        dict_probs = {
            "1": p_1, "X": p_X, "2": p_2,
            "1X": p_1 + p_X,
            "Over1.5": np.sum((goles_loc + goles_vis) > 1.5) / self.num_sim,
            "Over2.5": np.sum((goles_loc + goles_vis) > 2.5) / self.num_sim,
            "BTTS": np.sum((goles_loc > 0) & (goles_vis > 0)) / self.num_sim,
            "Tarjetas_Prom": np.mean(tarjetas_sim)
        }

        prob_real = dict_probs.get(p['tipo_mercado'], 0)
        cuota = p['cuota_casa']
        prob_casa = 1 / cuota
        ventaja = prob_real - prob_casa

        # Criterio de Kelly (1/4 Kelly)
        b = cuota - 1
        f_kelly = (b * prob_real - (1 - prob_real)) / b if b > 0 else 0
        stake_kelly_cop = max(0, f_kelly * 0.25 * self.bankroll)

        ganancia_1m = (self.bankroll * cuota) - self.bankroll

        return {
            "partido": f"{p['local']} vs {p['visitante']}",
            "mercado": p['tipo_mercado'],
            "cuota": cuota,
            "prob_real": prob_real * 100,
            "ventaja": ventaja * 100,
            "ganancia_1m": ganancia_1m,
            "stake_kelly_cop": stake_kelly_cop,
            "noticias_alerta": noticias,
            "xg_ajustado_loc": xg_loc_final,
            "tarjetas": dict_probs["Tarjetas_Prom"]
        }

# Ejemplo de prueba
if __name__ == "__main__":
    bot = BotGiga24Siete(bankroll_cop=1000000)
    
    partido_live = {
        "local": "Junior", "visitante": "América de Cali",
        "xg_loc_base": 2.10, "xg_vis_base": 0.90,
        "aforo_pct": 95, "crece_con_hinchada": True,
        "promedio_tarjetas_ref": 5.8, "tipo_mercado": "1X", "cuota_casa": 1.25
    }
    
    res = bot.simular_con_noticias_247(partido_live)
    print("==========================================================")
    print(f"📡 ANALIZADOR EN TIEMPO REAL 24/7: {res['partido']}")
    print("==========================================================")
    print(f"• Mercado: {res['mercado']} @ Cuota {res['cuota']}")
    print(f"• Probabilidad Estimada: {res['prob_real']:.2f}% | Ventaja Real: +{res['ventaja']:.2f}%")
    print(f"• Retorno Esperado Inversión $1M: ${res['ganancia_1m']:,.0f} COP")
    print(f"• Sugerencia Kelly (Seguridad): ${res['stake_kelly_cop']:,.0f} COP")
    print(f"• Pronóstico Árbitro: ~{res['tarjetas']:.1f} tarjetas en el partido")

