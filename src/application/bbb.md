# 📘 Documentazione Schema XML Custom (v2)

Questo documento descrive i tag e gli attributi del DSL XML per la definizione di interfacce UI dichiarative.

---

# 🧠 Filosofia

Il sistema separa:

* **Struttura** → tag XML
* **Comportamento** → eventi
* **Aspetto (UI)** → attributi semantici (`align`, `variant`, ecc.)
* **Escape hatch** → `class` (facoltativo)

---

# 🧩 Attributi Globali

| Attributo | Valori                     | Descrizione               |
| --------- | -------------------------- | ------------------------- |
| id        | string                     | Identificatore univoco    |
| class     | string                     | CSS raw (fallback)        |
| width     | px, %, token               | Larghezza                 |
| height    | px, %, token               | Altezza                   |
| padding   | xs, sm, md, lg, xl, numero | Spazio interno            |
| margin    | xs, sm, md, lg, xl, numero | Spazio esterno            |
| expand    | boolean                    | Occupa spazio disponibile |

---

# 🎨 Attributi UI (NUOVI 🔥)

| Attributo  | Valori                                               | Descrizione              |
| ---------- | ---------------------------------------------------- | ------------------------ |
| layout     | row, column, stack                                   | Layout principale        |
| justify    | start, center, end, between, around                  | Allineamento orizzontale |
| align      | start, center, end                                   | Allineamento verticale   |
| spacing    | xs, sm, md, lg, xl                                   | Gap tra elementi         |
| size       | xs, sm, md, lg, xl, hero                             | Scala componente         |
| variant    | primary, secondary, outline, ghost, gradient         | Variante visiva          |
| tone       | default, primary, secondary, success, warning, error | Colore semantico         |
| background | surface, surface-low, dark, glass                    | Background               |
| border     | none, subtle, strong                                 | Bordo                    |
| radius     | none, sm, md, lg, full                               | Arrotondamento           |
| shadow     | none, sm, md, lg, xl                                 | Ombra                    |
| text-align | left, center, right                                  | Allineamento testo       |
| weight     | light, normal, medium, bold, black                   | Peso font                |
| position   | static, relative, absolute, fixed-top                | Posizionamento           |
| responsive | md:hidden, lg:flex                                   | Comportamento responsive |

---

# ⚡ Eventi

| Attributo    | Descrizione |
| ------------ | ----------- |
| event-click  | funzione    |
| event-change | funzione    |

---

# 🧱 TAGS

---

## Window

Root o contenitore principale.

```xml
<Window layout="column" background="dark" color="white" />
```

**Attributi:**

* type: page, dialog, embed
* layout, background, justify, align

---

## Navigation

Barra di navigazione.

```xml
<Navigation position="fixed-top" justify="between" align="center" />
```

**Attributi:**

* type: bar, breadcrumb, tab
* orientation: horizontal, vertical

---

## Container

Contenitore con vincoli.

```xml
<Container type="fluid" align="center" />
```

---

## Row / Column / Stack

```xml
<Row justify="between" align="center" spacing="md" />
<Column spacing="lg" />
<Stack spacing="sm" />
```

---

## Group

Raggruppamento logico.

```xml
<Group type="list" orientation="horizontal" spacing="md" />
```

---

## Text

```xml
<Text type="h1" weight="black" text-align="center" size="hero" />
```

**type:**

* h1–h6, p, span, code, pre

---

## Action

```xml
<Action type="button" variant="primary" value="Click" />
```

**type:**

* button, link, submit

---

## Input

```xml
<Input type="text" placeholder="Email" required="true" />
```

---

## Card

```xml
<Card variant="elevated" padding="lg" />
```

---

## Media

```xml
<Media type="image" src="img.jpg" />
```

---

## Icon

```xml
<Icon name="close" size="sm" />
```

---

## Divider

```xml
<Divider />
```

---

## View

```xml
<View route="/home" />
```

---

## Messenger / Message

```xml
<Messenger>
  <Message type="success" value="Done!" />
</Messenger>
```

---

## Storekeeper

```xml
<Storekeeper repository="users" method="get" limit="10" />
```

---

## Defender

```xml
<Defender />
```

---

# 🧠 ESEMPIO COMPLETO

```xml
<Window layout="column" background="dark">

  <Navigation justify="between" align="center" padding="lg">

    <Group orientation="horizontal" spacing="md">
      <Text value="OMNIPORT" weight="black" size="lg" />
      <Action type="link" value="Docs" />
    </Group>

    <Action type="button" variant="primary" value="Start" />

  </Navigation>

  <View layout="column" align="center" justify="center" height="screen">

    <Text type="h1" size="hero" text-align="center">
      Hello World
    </Text>

  </View>

</Window>
```