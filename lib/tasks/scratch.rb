require_relative "../scrapers/data_fetcher"
require_relative "../path_helper"
require_relative "../services/openai"
require_relative "../services/google_gemini"
require_relative "../validators/city_directory"
require_relative "../core/crawler"

namespace :scratch do
  desc "Fetch data using Scrapers::DataFetcher"
  task :fetch do |_t, args|
    url = "https://seattle.gov/mayor/about"
    destination_dir = PathHelper.project_path("./testing")

    begin
      fetcher = Scrapers::DataFetcher.new
      openai_service = Services::Openai.new
      result = fetcher.extract_content(url, destination_dir)
      response = openai_service.extract_city_info(result, url)

      puts "Successfully fetched data to: #{result}"
      puts "Response: #{response}"
    rescue StandardError => e
      puts "Error: #{e.message}"
      puts e.backtrace
      exit 1
    end
  end

  desc "something about validation"
  task :validate do |_t, args|
    state = "wa"
    gnis = "2411856"

    # city_entry = CityScrape::StateManager.get_city_entry_by_gnis(state, gnis)
    # city_directory_to_validate = CityScrape::CityManager.get_city_directory(state, city_entry)
    # Validators::CityDirectory.validate_directory(state, gnis, city_directory_to_validate)
  end

  desc "test new crawler"
  task :crawl do |_t, args|
    state = "wa"
    gnis = "2411856"

    city_entry = CityScrape::StateManager.get_city_entry_by_gnis(state, gnis)
    keyword_groups = [
      { name: "council members", keywords: [
        "mayor and city council",
        "meet the council",
        "city council members",
        "council districts",
        "council members",
        "councilmembers",
        "city council",
        "council"
      ] }, { name: "city leader", keywords: [
        "mayor",
        "meet the mayor",
        "about the mayor",
        "council president"
      ] }, { name: "common", keywords: %w[
        index
        government
      ] }
    ]
    # Crawler.crawl("https://www.seattle.gov/", keyword_groups: keyword_groups)
    # search_query = "#{city_entry.name} #{state} council members"
    # urls = Services::Brave.get_search_result_urls(search_query, "https://www.seattle.gov/")

    puts urls
  end

  desc "test google gemini"
  task :gemini do |_t, args|
    google_gemini = Services::GoogleGemini.new
    city = "seattle"
    url = "https://www.seattle.gov/"
    gemini_thinks = google_gemini.get_city_officials(city, url)
    city_entry = CityScrape::StateManager.get_city_entry_by_gnis("wa", "2411856")
    city_directory = CityScrape::CityManager.get_city_directory("wa", city_entry)
    city_path = CityScrape::CityManager.get_city_path("wa", city_entry)

    simple_city_directory = city_directory["people"].map do |person|
      formatted = Utils.format_simple(person)
      formatted.reject { |k, _v| k == "image" }
    end

    directories_file_path = File.join(city_path, "directories")

    FileUtils.mkdir_p(directories_file_path)
    File.write(File.join(directories_file_path, "directory.gemini.yml"), simple_city_directory.to_yaml)
  end
end
