# load packages ----------------------------------------------------------------
library(tidyverse)
library(openintro)
library(unvotes)
library(lubridate)

# Frozen data authority: CRAN unvotes 0.2.0, the release active when this
# figure was added to the book in 2019. Deterministic non-R replay:
# regenerate_id.py

# plot unvotes by issues -------------------------------------------------------

un_votes %>%
  mutate(country = case_when(
    country == "United States of America" ~ "AS",
    country == "Mexico" ~ "Meksiko",
    country == "Canada" ~ "Kanada",
    TRUE ~ country
  )) %>%
  filter(country %in% c("AS", "Meksiko", "Kanada")) %>%
  inner_join(un_roll_calls, by = "rcid") %>%
  inner_join(un_roll_call_issues, by = "rcid") %>%
  mutate(
    issue = case_when(
      issue == "Arms control and disarmament" ~ "Pengendalian dan pelucutan senjata",
      issue == "Colonialism" ~ "Kolonialisme",
      issue == "Economic development" ~ "Pembangunan ekonomi",
      issue == "Human rights" ~ "Hak asasi manusia",
      issue == "Nuclear weapons and nuclear material" ~ "Senjata dan bahan nuklir",
      issue == "Palestinian conflict" ~ "Konflik Palestina",
      TRUE ~ issue
    ),
    country = factor(country, levels = c("Kanada", "Meksiko", "AS")),
    issue = factor(
      issue,
      levels = c(
        "Pengendalian dan pelucutan senjata",
        "Kolonialisme",
        "Pembangunan ekonomi",
        "Hak asasi manusia",
        "Senjata dan bahan nuklir",
        "Konflik Palestina"
      )
    ),
    vote = fct_relevel(vote, "yes", "no", "abstain")
    ) %>%
  group_by(country, year = year(date), issue) %>%
  summarize(
    votes = n(),
    percent_yes = mean(vote == "yes")
  ) %>%
  filter(votes > 5) %>%  # only use records where there are more than 5 votes
  ggplot(mapping = aes(x = year, y = percent_yes, color = country)) +
    geom_point(alpha = 0.5) +
    geom_smooth(method = "loess", se = FALSE) +
    facet_wrap(~ issue) +
    labs(
      y = "Proporsi suara Ya",
      x = "Tahun",
      color = "Negara"
    ) +
    theme_minimal() +
    scale_color_manual(
      values = c("Kanada" = COL[1,1], "Meksiko" = COL[2,1], "AS" = COL[4,1])
    )

# save plot --------------------------------------------------------------------
ggsave(
  here::here("ch_intro_to_data", "figures", "eoce", "unvotes", "unvotes.png"),
  width = 7,
  height = 4
)
