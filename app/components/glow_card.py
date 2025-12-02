import streamlit as st


class GlowCard:
    """
    Robust 'Sandwich' Glow Effect.
    Now supports a '.glow-large' class for big elements like tables.
    """

    @staticmethod
    def _inject_code():
        # Inject CSS and JS once
        st.markdown(
            """
        <style>
            /* --- STANDARD CARD (Small/Medium) --- */
            .glow-card-wrapper {
                position: relative;
                border-radius: 12px;
                padding: 1px; /* Standard border width */
                background: #1f1f1f;
                overflow: hidden;
                margin-bottom: 14px;
                box-shadow: 0 4px 10px rgba(0,0,0,0.2);
                transition: background 0.3s;
            }

            /* Standard Spotlight */
            .glow-card-wrapper::before {
                content: "";
                position: absolute;
                top: 0; left: 0; right: 0; bottom: 0;
                border-radius: 12px;
                z-index: 1;
                opacity: 0;
                transition: opacity 0.3s;
                /* Standard Size: 600px */
                background: radial-gradient(
                    600px circle at var(--x, 50%) var(--y, 50%),
                    rgba(255, 255, 255, 0.5),
                    rgba(220, 20, 60, 0.4),
                    transparent 40%
                );
            }

            /* --- LARGE VARIANT (Tables) --- */
            /* Use this class <div class="glow-card-wrapper glow-large"> */
            .glow-card-wrapper.glow-large {
                padding: 2px; /* Thicker border for better visibility */
            }

            .glow-card-wrapper.glow-large::before {
                /* Larger Spotlight: 1200px to cover big tables */
                /* Brighter Colors: 0.7 opacity */
                background: radial-gradient(
                    1200px circle at var(--x, 50%) var(--y, 50%),
                    rgba(255, 255, 255, 0.8),
                    rgba(255, 50, 50, 0.6),
                    transparent 45%
                );
            }

            /* --- SHARED STYLES --- */
            .glow-card-wrapper:hover::before {
                opacity: 1;
            }

            .glow-card-content {
                position: relative;
                background: #141414;
                border-radius: 11px; /* Slightly smaller than wrapper */
                padding: 16px 20px;
                height: 100%;
                z-index: 2;
            }

            /* Typography */
            .gc-title {
                color: #ff4d4d;
                font-size: 0.75rem;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 1px;
                margin-bottom: 6px;
                font-family: sans-serif;
            }
            .gc-value {
                color: #ffffff;
                font-size: 1.3rem;
                font-weight: 600;
                font-family: serif;
            }
        </style>

        <script>
        (function() {
            function onMouseMove(e) {
                const cards = document.querySelectorAll(".glow-card-wrapper");
                
                cards.forEach(card => {
                    const rect = card.getBoundingClientRect();
                    const x = e.clientX - rect.left;
                    const y = e.clientY - rect.top;

                    card.style.setProperty("--x", x + "px");
                    card.style.setProperty("--y", y + "px");
                });
            }

            if (window.f1GlowScriptLoaded) return;
            window.addEventListener("mousemove", onMouseMove);
            window.f1GlowScriptLoaded = true;
        })();
        </script>
        """,
            unsafe_allow_html=True,
        )

    @staticmethod
    def render(title, value):
        GlowCard._inject_code()

        st.markdown(
            f"""
        <div class="glow-card-wrapper">
            <div class="glow-card-content">
                <div class="gc-title">{title}</div>
                <div class="gc-value">{value}</div>
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )
