"""Adds 'The team' section to About (after the host section). Idempotent. Usage: python3 team.py <About.dc.html>"""
import sys
f = sys.argv[1]
s = open(f).read()
if 'aria-labelledby="team"' in s:
    print('already'); sys.exit()
MONO = "font-family: 'PP Monument Extended', 'Arial Black', sans-serif;"
s = s.replace(f'<p style="margin: 0; {MONO} font-size: 12px; font-weight: 800; letter-spacing: 0.12em; color: #fecb7a;">YOUR HOST</p>',
              f'<p style="margin: 0; {MONO} font-size: 12px; font-weight: 800; letter-spacing: 0.12em; color: #fecb7a;">HOST &amp; CO-FOUNDER</p>', 1)
assert 'HOST &amp; CO-FOUNDER' in s

PEOPLE = [
    ('A', 'Alexandra Lukey', 'CO-FOUNDER',
     'Alexandra dances herself, and a show where DanceSport talks about itself in the open was close to her heart from day one. Alongside Break The Routine she is co-founding InBetween, the app that turns what your coach says in a lesson into focus points you keep working on between lessons.',
     'Alexandra, co-founder of Break The Routine'),
    ('L', 'Loïc Viatte', 'CO-FOUNDER',
     'For Loïc, Break The Routine is a free-expression project close to his heart: a place where DanceSport can speak openly about itself. Alongside the show he is co-founding InBetween with Alexandra.',
     'Loïc Viatte, co-founder of Break The Routine'),
    ('G', 'Georgia', 'TEAM',
     '[Georgia’s introduction is coming soon.]',
     'Georgia, Break The Routine team'),
]
cards = []
for ini, name, role, bio, alt in PEOPLE:
    cards.append(f'''        <article style="display: flex; flex-direction: column; gap: 18px; min-width: 0;">
          <div role="img" aria-label="{alt}" style="position: relative; aspect-ratio: 1 / 1; max-width: 100%; overflow: hidden; background: repeating-linear-gradient(90deg, #0e0705 0px, #0e0705 14px, #140b07 14px, #140b07 18px); border: 1px solid rgba(254,203,122,0.18);">
            <span aria-hidden="true" style="position: absolute; left: 0; right: 0; top: 50%; transform: translateY(-50%); text-align: center; {MONO} font-size: clamp(72px, 9vw, 120px); font-weight: 800; line-height: 1; color: rgba(254,203,122,0.16);">{ini}</span>
            <div aria-hidden="true" style="position: absolute; inset: 0; background: linear-gradient(180deg, rgba(0,0,0,0) 55%, rgba(223,191,100,0.45) 100%);"></div>
          </div>
          <div style="display: flex; flex-direction: column; gap: 8px;">
            <p style="margin: 0; {MONO} font-size: 11px; font-weight: 800; letter-spacing: 0.12em; color: #fecb7a;">{role}</p>
            <h3 style="margin: 0; {MONO} font-size: 24px; font-weight: 800; line-height: 1.1; color: #ffffff;">{name}</h3>
            <p style="margin: 0; font-size: 16px; line-height: 1.55; color: #c9b8a6;">{bio}</p>
          </div>
        </article>''')

section = f'''
    <section aria-labelledby="team" style="max-width: 1440px; margin: 0 auto; box-sizing: border-box; padding: 96px clamp(16px, 4vw, 56px); display: flex; flex-direction: column; gap: 40px;">
      <div style="display: flex; flex-wrap: wrap; gap: 16px 64px; align-items: flex-end; justify-content: space-between;">
        <div style="flex: 1 1 480px; min-width: 0; display: flex; flex-direction: column; gap: 12px;">
          <p style="margin: 0; {MONO} font-size: 12px; font-weight: 800; letter-spacing: 0.12em; color: #fecb7a;">THE TEAM</p>
          <h2 id="team" style="margin: 0; {MONO} font-size: clamp(26px, 3vw, 42px); font-weight: 800; line-height: 1.08; text-wrap: balance;">The people behind the show</h2>
        </div>
        <p style="margin: 0; flex: 0 1 420px; min-width: 0; color: #c9b8a6;">Break The Routine was founded by Marius, Alexandra and Loïc, three people who live DanceSport from different sides of the floor.</p>
      </div>
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 40px 28px;">
{chr(10).join(cards)}
      </div>
    </section>
'''
anchor = '    <section aria-labelledby="guest"'
assert s.count(anchor) == 1
s = s.replace(anchor, section.lstrip('\n') + '\n' + anchor, 1)
open(f, 'w').write(s)
print('ok')
